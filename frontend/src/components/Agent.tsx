import { useRef, useState } from "react";
import {
  applyEvent,
  initialCards,
  type NodeCard,
  type CardStatus,
} from "./agentStream.ts";
import { NODE_ANNOTATIONS } from "./demo_annotations.ts";
import { INTRO, nodeNarrative, finalNarrative } from "./narrative.ts";
import { nodeInputRows } from "./slide.ts";

interface EvalResult {
  reason_hit: boolean;
  reason_code_pred?: string | null;
  reason_code_gold?: string | null;
  supported_actions?: number;
  total_actions?: number;
}

type Phase = "idle" | "running" | "interrupt" | "approving" | "done" | "error";

interface StartMeta {
  thread_id: string;
  event_id: number | null;
  sim_now: string | null;
  line_id: string;
  mode: string;
}

interface Action {
  title?: string;
  description?: string;
  rationale?: string;
  level?: string;
  confidence?: number;
}

interface Gold {
  reason_code?: string;
  duration_min?: number;
}

interface JudgeResult {
  title: string;
  verified: boolean;
  judge_note: string;
}

const STATUS_STYLE: Record<CardStatus, { dot: string; label: string; text: string }> = {
  wartend: { dot: "bg-gray-600", label: "wartend", text: "text-gray-500" },
  "läuft": { dot: "bg-teal-600 animate-pulse", label: "läuft", text: "text-teal-500" },
  fertig: { dot: "bg-salbei-500", label: "fertig", text: "text-salbei-500" },
  freigabe: { dot: "bg-wein-500 animate-pulse", label: "Freigabe", text: "text-wein-500" },
};

/** Judge-Ergebnis je Maßnahme als Badge; judge_note beim Hover/als title. */
function JudgeBadge({ result }: { result?: JudgeResult }) {
  if (!result) return null;
  const ok = result.verified;
  return (
    <span
      data-testid={ok ? "judge-ok" : "judge-fail"}
      title={result.judge_note}
      className={[
        "inline-flex items-center px-1.5 py-0.5 rounded text-[10px] cursor-help whitespace-nowrap",
        ok ? "bg-salbei-500/15 text-salbei-500" : "bg-wein-600/25 text-wein-500",
      ].join(" ")}
    >
      {ok ? "✓ vom Judge bestätigt" : "✗ vom Judge nicht bestätigt"}
    </span>
  );
}

export default function Agent() {
  const [eventId, setEventId] = useState(360);
  const [phase, setPhase] = useState<Phase>("idle");
  const [cards, setCards] = useState<NodeCard[]>(initialCards());
  const [meta, setMeta] = useState<StartMeta | null>(null);
  const [interruptPayload, setInterruptPayload] = useState<Record<string, unknown> | null>(null);
  const [approval, setApproval] = useState<{ approved: boolean } | null>(null);
  const [gold, setGold] = useState<Gold | null>(null);
  const [evalResult, setEvalResult] = useState<EvalResult | null>(null);
  const [error, setError] = useState("");
  const [comment, setComment] = useState("");
  const [showNotes, setShowNotes] = useState(true);
  const [openCard, setOpenCard] = useState<string | null>(null);

  const esRef = useRef<EventSource | null>(null);
  const phaseRef = useRef<Phase>("idle");
  const retriedRef = useRef(false);
  const setPhaseSync = (p: Phase) => {
    phaseRef.current = p;
    setPhase(p);
  };

  const openStream = () => {
    const es = new EventSource(`/investigations/stream?line_id=L1&event_id=${eventId}`);
    esRef.current = es;

    es.addEventListener("start", (e) => {
      setMeta(JSON.parse((e as MessageEvent).data));
    });
    es.addEventListener("node", (e) => {
      const d = JSON.parse((e as MessageEvent).data);
      setCards((prev) => applyEvent(prev, { kind: "node", node: d.node, payload: d.payload }));
    });
    es.addEventListener("interrupt", (e) => {
      const d = JSON.parse((e as MessageEvent).data);
      setCards((prev) => applyEvent(prev, { kind: "interrupt", payload: d.payload }));
      setInterruptPayload(d.payload ?? {});
      setPhaseSync("interrupt");
      es.close(); // Stream endet am Freigabeknoten – sonst würde EventSource neu verbinden
    });
    es.onerror = () => {
      es.close();
      // am Freigabeknoten/Abschluss ist das Schließen erwartet – kein Fehler
      if (phaseRef.current === "interrupt" || phaseRef.current === "done") return;
      if (!retriedRef.current) {
        retriedRef.current = true; // genau ein Reconnect-Versuch
        setTimeout(openStream, 800);
        return;
      }
      setError("Verbindung zum SSE-Stream abgebrochen (nach einem Reconnect-Versuch).");
      setPhaseSync("error");
    };
  };

  const start = () => {
    esRef.current?.close();
    retriedRef.current = false;
    setCards(applyEvent(initialCards(), { kind: "start" }));
    setMeta(null);
    setInterruptPayload(null);
    setApproval(null);
    setGold(null);
    setEvalResult(null);
    setError("");
    setOpenCard(null);
    setPhaseSync("running");
    openStream();
  };

  const decide = async (approved: boolean) => {
    if (!meta) return;
    setPhaseSync("approving");
    try {
      const r = await fetch("/investigations/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          thread_id: meta.thread_id,
          approved,
          comment,
          approved_action_titles: [],
          event_id: meta.event_id,
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      // reason_hit + belegte Maßnahmen kommen serverseitig aus replay.score (nur bei bekanntem Gold)
      setEvalResult((data?.eval as EvalResult) ?? null);
      setApproval({ approved });
      setPhaseSync("done");
      // Eval nach dem Lauf: Hypothese gegen die Gold-Wahrheit (kein Leck während des Laufs)
      if (meta.event_id != null) {
        try {
          const g = await fetch(`/investigations/gold/${meta.event_id}`);
          if (g.ok) setGold(await g.json());
        } catch {
          /* Eval ist optional */
        }
      }
    } catch (e) {
      setError(`Freigabe fehlgeschlagen: ${String(e)}`);
      setPhaseSync("error");
    }
  };

  const actions: Action[] = Array.isArray(interruptPayload?.actions)
    ? (interruptPayload!.actions as Action[])
    : [];
  // Judge-Ergebnisse: bevorzugt aus der Interrupt-Payload, sonst aus der Beleg-Prüfung-Karte
  const judgeResults: JudgeResult[] = Array.isArray(interruptPayload?.judge_results)
    ? (interruptPayload!.judge_results as JudgeResult[])
    : Array.isArray(cards.find((c) => c.id === "check_evidence")?.payload?.judge_results)
      ? (cards.find((c) => c.id === "check_evidence")!.payload!.judge_results as JudgeResult[])
      : [];
  const judgeByTitle = (title?: string): JudgeResult | undefined =>
    judgeResults.find((r) => r.title === title);
  const hypothesis = (cards.find((c) => c.id === "narrow_cause")?.payload?.hypothesis ??
    {}) as Record<string, unknown>;
  const predictedReason = hypothesis.reason_code as string | undefined;
  const reasonHit =
    gold && predictedReason ? gold.reason_code === predictedReason : null;

  // zuletzt abgeschlossene Karte (hat echte Daten) treibt den laufbegleitenden Erzähltext
  const lastDoneCard =
    [...cards].reverse().find((c) => c.status === "fertig" || c.status === "freigabe") ?? null;
  const narrativeText =
    phase === "done" && approval
      ? finalNarrative({
          approved: approval.approved,
          reasonHit: evalResult ? evalResult.reason_hit : reasonHit,
          reasonCodePred: evalResult?.reason_code_pred ?? predictedReason ?? null,
          reasonCodeGold: evalResult?.reason_code_gold ?? gold?.reason_code ?? null,
          supportedActions: evalResult?.supported_actions ?? null,
        })
      : phase === "error"
        ? ""
        : lastDoneCard
          ? nodeNarrative(lastDoneCard)
          : phase === "running"
            ? INTRO
            : "";

  return (
    <div className="space-y-5 max-w-3xl">
      {/* Steuerzeile */}
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="text-gray-400 text-xs block mb-1">Ereignis-ID</label>
          <input
            type="number"
            min={1}
            value={eventId}
            onChange={(e) => setEventId(Number(e.target.value))}
            className="w-24 bg-gray-800 border border-gray-600 rounded px-2 py-1.5 text-sm focus:outline-none focus:border-teal-600"
          />
        </div>
        <button
          onClick={start}
          disabled={phase === "running" || phase === "approving"}
          className="px-4 py-1.5 rounded bg-teal-700 hover:bg-teal-600 text-white text-sm disabled:opacity-50 transition-colors"
        >
          {phase === "running" ? "Läuft…" : "Untersuchung starten"}
        </button>
        <label className="flex items-center gap-2 text-xs text-gray-400 ml-auto cursor-pointer select-none">
          <input
            type="checkbox"
            checked={showNotes}
            onChange={(e) => setShowNotes(e.target.checked)}
            className="accent-teal-600"
          />
          Demo-Notizen {showNotes ? "(Präsentationsmodus)" : "(Produktansicht)"}
        </label>
      </div>

      {/* Lauf-Metadaten: Modus wird angezeigt, nicht gesetzt */}
      {meta && (
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-gray-500">
          <span>
            Modus{" "}
            <span
              className={meta.mode === "live" ? "text-wein-500" : "text-teal-500"}
              title="bestimmt der Backend-LLM_MODE, nicht das Cockpit"
            >
              {meta.mode}
            </span>
          </span>
          <span>Ereignis {meta.event_id ?? "–"}</span>
          <span>Replay-Uhr {meta.sim_now ?? "–"}</span>
          <span>Linie {meta.line_id}</span>
        </div>
      )}

      {/* Fortschrittsleiste */}
      <div className="flex items-center gap-1">
        {cards.map((c, i) => (
          <div key={c.id} className="flex items-center flex-1 last:flex-none">
            <span
              className={["inline-block w-3 h-3 rounded-full shrink-0", STATUS_STYLE[c.status].dot].join(" ")}
              title={`${c.label}: ${STATUS_STYLE[c.status].label}`}
            />
            {i < cards.length - 1 && <span className="h-px flex-1 bg-gray-700 mx-1" />}
          </div>
        ))}
      </div>

      {/* Laufbegleitender Erzähltext: aktive bzw. zuletzt abgeschlossene Karte, sichtbar per Default */}
      {narrativeText && (
        <div
          data-testid="narrative"
          className="rounded-lg border border-gray-700 bg-gray-900/60 px-4 py-3 min-h-[3rem] flex items-center"
        >
          <p
            key={narrativeText}
            className="text-sm text-gray-200 leading-relaxed narrative-fade"
          >
            {narrativeText}
          </p>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-wein-600 bg-wein-700/20 p-3 text-wein-500 text-xs">
          {error}
        </div>
      )}

      {/* Schritt-Karten je Knoten */}
      <div className="space-y-2">
        {cards.map((c) => {
          const st = STATUS_STYLE[c.status];
          const ann = NODE_ANNOTATIONS[c.id];
          const isOpen = openCard === c.id;
          const inputRows = isOpen ? nodeInputRows(c.id, cards, meta) : [];
          return (
            <div key={c.id} className="bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
              <button
                onClick={() => setOpenCard(isOpen ? null : c.id)}
                className="w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-gray-800/40"
              >
                <span className={["inline-block w-2.5 h-2.5 rounded-full shrink-0", st.dot].join(" ")} />
                <span className="text-gray-200 text-sm font-medium w-52 shrink-0">{c.label}</span>
                <span className="text-gray-400 text-xs truncate flex-1">
                  {c.summary || <span className="text-gray-600">—</span>}
                </span>
                <span className={["text-xs shrink-0", st.text].join(" ")}>{st.label}</span>
              </button>

              {c.id === "check_evidence" && judgeResults.length > 0 && (
                <div className="px-4 pb-2 pt-1 space-y-1.5 border-t border-gray-800/60">
                  {judgeResults.map((r, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      <JudgeBadge result={r} />
                      <span className="text-gray-400 truncate">{r.title}</span>
                    </div>
                  ))}
                  {judgeResults.some((r) => !r.verified) && (
                    <p className="text-[11px] text-gray-500 pt-0.5">
                      Hinweis: nicht bestätigte Maßnahmen werden nicht automatisch verworfen – der Mensch entscheidet an der Freigabe.
                    </p>
                  )}
                </div>
              )}

              {/* Präsentations-Glance: Funktion inline, wenn Demo-Notizen an und Karte zu */}
              {showNotes && ann && !isOpen && (
                <div className="px-4 pb-2 pt-0 border-t border-gray-800/60">
                  <p className="text-xs text-gray-400">
                    <span className="text-teal-500 font-semibold">Funktion:</span> {ann.funktion}
                  </p>
                </div>
              )}

              {/* Folie: Eingang · Transformation · Bewertung (aufgeklappt) */}
              {isOpen && (
                <div className="border-t border-gray-800/60 px-4 py-3 space-y-3 text-xs">
                  <div>
                    <p className="text-teal-500 font-semibold mb-1">Eingang</p>
                    {inputRows.length ? (
                      <table className="w-full">
                        <tbody>
                          {inputRows.map((r, i) => (
                            <tr key={i}>
                              <td className="text-gray-500 pr-3 align-top whitespace-nowrap">{r.label}</td>
                              <td className="text-gray-300">{r.value}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    ) : (
                      <p className="text-gray-600">—</p>
                    )}
                  </div>
                  <div>
                    <p className="text-salbei-500 font-semibold mb-1">Transformation</p>
                    <p className="text-gray-300">{c.summary || "—"}</p>
                    {ann && <p className="text-gray-500 mt-0.5">Weg: {ann.funktion}</p>}
                  </div>
                  {ann && (
                    <div>
                      <p className="text-wein-500 font-semibold mb-1">Bewertung</p>
                      <p className="text-gray-300">{ann.bewertung}</p>
                      <p className="text-gray-500 mt-0.5">Weitere Schritte: {ann.ausblick}</p>
                    </div>
                  )}
                  {c.payload && (
                    <details className="text-gray-500">
                      <summary className="cursor-pointer select-none">Rohdaten</summary>
                      <pre className="mt-1 whitespace-pre-wrap max-h-56 overflow-auto text-gray-400">
                        {JSON.stringify(c.payload, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Freigabe erforderlich */}
      {phase === "interrupt" && (
        <div className="rounded-lg border border-wein-600 bg-gray-900 p-4 space-y-3">
          <p className="text-wein-500 text-xs font-semibold uppercase tracking-wide">
            Freigabe erforderlich – der Agent empfiehlt, er führt nicht aus
          </p>
          <div className="space-y-2">
            {actions.map((a, i) => {
              const jr = judgeByTitle(a.title);
              return (
                <div key={i} className="rounded border border-gray-700 p-2 text-xs">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-gray-200 font-medium">{a.title}</p>
                    <JudgeBadge result={jr} />
                  </div>
                  {a.description && <p className="text-gray-400 mt-0.5">{a.description}</p>}
                  {a.rationale && (
                    <p className="text-salbei-500 mt-0.5">Beleg: {a.rationale}</p>
                  )}
                  {jr && !jr.verified && (
                    <p className="text-wein-500 mt-0.5">Judge: {jr.judge_note}</p>
                  )}
                </div>
              );
            })}
            {actions.length === 0 && (
              <p className="text-gray-500 text-xs">Keine Maßnahmen im Interrupt-Payload.</p>
            )}
          </div>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Kommentar (optional)"
            rows={2}
            className="w-full bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs focus:outline-none focus:border-teal-600 resize-none"
          />
          <div className="flex gap-3">
            <button
              onClick={() => decide(true)}
              className="px-4 py-1.5 rounded bg-teal-700 hover:bg-teal-600 text-white text-sm"
            >
              Freigeben
            </button>
            <button
              onClick={() => decide(false)}
              className="px-4 py-1.5 rounded bg-wein-600 hover:bg-wein-500 text-white text-sm"
            >
              Ablehnen
            </button>
          </div>
        </div>
      )}

      {/* Abschluss + Eval */}
      {phase === "done" && approval && (
        <div className="rounded-lg border border-gray-700 bg-gray-900 p-4 space-y-2">
          <p
            className={[
              "text-xs font-semibold uppercase tracking-wide",
              approval.approved ? "text-teal-500" : "text-wein-500",
            ].join(" ")}
          >
            {approval.approved
              ? "Freigegeben – regulärer Abschluss"
              : "Abgelehnt – sauberer Abbruch, kein Maßnahmen-Abschluss"}
          </p>
          <p className="text-gray-400 text-xs">
            Entscheidung rollenbasiert im Audit protokolliert (jeder Werkzeugaufruf und jede Freigabe).
          </p>
          {gold && (
            <div className="text-xs text-gray-400 border-t border-gray-800 pt-2">
              <span className="text-gray-500">Eval gegen Gold: </span>
              Hypothese <span className="text-gray-200">{predictedReason ?? "–"}</span> vs. Gold{" "}
              <span className="text-gray-200">{gold.reason_code ?? "–"}</span> ·{" "}
              {reasonHit === null ? (
                "–"
              ) : reasonHit ? (
                <span className="text-salbei-500">reason_hit ✓</span>
              ) : (
                <span className="text-wein-500">reason_hit ✗</span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
