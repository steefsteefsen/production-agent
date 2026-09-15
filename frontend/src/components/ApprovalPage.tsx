import { useEffect, useRef, useState } from "react";

/**
 * Eigenständige Freigabe-Seite (Route /freigabe): erscheint, sobald der Graph am interrupt() hält.
 * Zeigt die beste Hypothese mit Konfidenzwert und Schwellenlinie (zur Laufzeit gelesen, nicht
 * hartkodiert), Maßnahmenkarten je mit Policy-Badge, Konfidenzbalken samt Schwellenmarkierung und
 * dem ORIGINAL-Belegtext aus dem Wartungsdokument. Hypothesen unter der Schwelle stehen sichtbar in
 * einer eigenen Karte ("zur Kenntnis, nicht empfohlen"). Der Mensch gibt hier frei oder lehnt ab.
 */

type Phase = "idle" | "running" | "interrupt" | "approving" | "done" | "error";

interface Action {
  title?: string;
  description?: string;
  rationale?: string;
  level?: string;
  confidence?: number;
  beleg_text?: string;
  beleg_quelle?: string;
  policy_notes?: string[];
}

interface JudgeResult {
  title: string;
  verified: boolean;
  judge_note: string;
}

interface StartMeta {
  thread_id: string;
  event_id: number | null;
  sim_now: string | null;
  line_id: string;
  mode: string;
}

interface Payload {
  actions?: Action[];
  hypothesis?: { reason_code?: string; confidence?: number; cause?: string };
  applied_threshold?: number | null;
  judge_results?: JudgeResult[];
}

function pct(x: number): string {
  return `${Math.round(x * 100)}%`;
}

/** Policy-Badge: inform (Diagnose, keine Freigabe nötig) vs. approval_required (Eingriff → Freigabe).
 * forbidden wird nie angezeigt – solche Maßnahmen filtert die Policy bereits im Backend heraus. */
function PolicyBadge({ level }: { level?: string }) {
  if (level === "forbidden") return null;
  const inform = level === "inform";
  return (
    <span
      data-testid="policy-badge"
      data-level={level ?? "approval_required"}
      className={[
        "inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium whitespace-nowrap",
        inform ? "bg-teal-500/15 text-teal-400" : "bg-amber-500/15 text-amber-400",
      ].join(" ")}
    >
      {inform ? "inform" : "approval_required"}
    </span>
  );
}

/** Konfidenzbalken mit Schwellenmarkierung: Füllbreite = Konfidenz, senkrechte Linie = Schwelle. */
function ConfidenceBar({ confidence, threshold }: { confidence: number; threshold: number }) {
  const above = confidence >= threshold;
  return (
    <div className="space-y-1" data-testid="confidence-bar">
      <div className="relative h-3 rounded bg-gray-800 overflow-hidden">
        <div
          className={["h-full rounded-l", above ? "bg-salbei-500" : "bg-amber-500/70"].join(" ")}
          style={{ width: pct(confidence) }}
        />
        <div
          data-testid="threshold-marker"
          title={`Schwelle ${pct(threshold)}`}
          className="absolute top-[-2px] bottom-[-2px] w-0.5 bg-wein-500"
          style={{ left: pct(threshold) }}
        />
      </div>
      <div className="flex justify-between text-[10px] text-gray-500">
        <span>
          Konfidenz <span className="text-gray-300">{pct(confidence)}</span>
        </span>
        <span>Schwelle {pct(threshold)}</span>
      </div>
    </div>
  );
}

function Belegtext({ action }: { action: Action }) {
  if (!action.beleg_text) {
    // Fallback nur, falls das Backend keinen Dokumentsatz liefert – dann wenigstens die Vorfall-ID.
    return action.rationale ? (
      <p className="text-xs text-gray-500 mt-2">Beleg: {action.rationale}</p>
    ) : null;
  }
  return (
    <blockquote
      data-testid="belegtext"
      className="mt-2 border-l-2 border-salbei-500/60 pl-3 py-1 text-xs text-gray-300 italic bg-gray-800/40 rounded-r"
    >
      „{action.beleg_text}"
      {action.beleg_quelle && (
        <span className="block not-italic text-[10px] text-gray-500 mt-1">
          Quelle: {action.beleg_quelle}
        </span>
      )}
    </blockquote>
  );
}

export default function ApprovalPage() {
  const params = new URLSearchParams(window.location.search);
  const [eventId, setEventId] = useState<number>(Number(params.get("event")) || 360);
  const [phase, setPhase] = useState<Phase>("idle");
  const [meta, setMeta] = useState<StartMeta | null>(null);
  const [payload, setPayload] = useState<Payload | null>(null);
  const [approved, setApproved] = useState<boolean | null>(null);
  const [comment, setComment] = useState("");
  const [error, setError] = useState("");

  const esRef = useRef<EventSource | null>(null);
  const phaseRef = useRef<Phase>("idle");
  const setPhaseSync = (p: Phase) => {
    phaseRef.current = p;
    setPhase(p);
  };

  const openStream = (evId: number) => {
    const es = new EventSource(`/investigations/stream?line_id=L1&event_id=${evId}`);
    esRef.current = es;
    es.addEventListener("start", (e) => setMeta(JSON.parse((e as MessageEvent).data)));
    es.addEventListener("interrupt", (e) => {
      const d = JSON.parse((e as MessageEvent).data);
      setPayload((d.payload ?? {}) as Payload);
      setPhaseSync("interrupt");
      es.close();
    });
    es.onerror = () => {
      es.close();
      if (phaseRef.current === "interrupt" || phaseRef.current === "done") return;
      setError("Verbindung zum SSE-Stream abgebrochen.");
      setPhaseSync("error");
    };
  };

  const start = (evId: number) => {
    esRef.current?.close();
    setMeta(null);
    setPayload(null);
    setApproved(null);
    setError("");
    setPhaseSync("running");
    openStream(evId);
  };

  // Auto-Start beim Öffnen der Seite – die Seite existiert, um die Freigabe zu zeigen.
  useEffect(() => {
    start(eventId);
    return () => esRef.current?.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const decide = async (ok: boolean) => {
    if (!meta) return;
    setPhaseSync("approving");
    try {
      const r = await fetch("/investigations/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          thread_id: meta.thread_id,
          approved: ok,
          comment,
          approved_action_titles: [],
          event_id: meta.event_id,
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      await r.json();
      setApproved(ok);
      setPhaseSync("done");
    } catch (e) {
      setError(`Freigabe fehlgeschlagen: ${String(e)}`);
      setPhaseSync("error");
    }
  };

  const threshold =
    typeof payload?.applied_threshold === "number" ? payload!.applied_threshold! : 0.6;
  const actions = payload?.actions ?? [];
  const judge = payload?.judge_results ?? [];
  const judgeByTitle = (t?: string) => judge.find((j) => j.title === t);
  const recommended = actions.filter((a) => (a.confidence ?? 0) >= threshold);
  const below = actions.filter((a) => (a.confidence ?? 0) < threshold);
  const hypoConf = payload?.hypothesis?.confidence ?? 0;
  const reason = payload?.hypothesis?.reason_code ?? "–";

  return (
    <div className="min-h-screen bg-gray-950 text-gray-200" data-testid="approval-page">
      <header className="bg-gray-900 border-b border-gray-700 px-6 py-3 flex items-center gap-4">
        <a href="/" className="text-teal-600 font-bold text-base tracking-wide hover:text-teal-400">
          Production Agent
        </a>
        <span className="text-gray-400 text-sm">Freigabe-Seite · Verpackungslinie L1</span>
        <div className="ml-auto flex items-end gap-2">
          <div>
            <label className="text-gray-500 text-[10px] block">Ereignis-ID</label>
            <input
              type="number"
              min={1}
              value={eventId}
              onChange={(e) => setEventId(Number(e.target.value))}
              className="w-20 bg-gray-800 border border-gray-600 rounded px-2 py-1 text-sm focus:outline-none focus:border-teal-600"
            />
          </div>
          <button
            onClick={() => start(eventId)}
            disabled={phase === "running" || phase === "approving"}
            className="px-3 py-1.5 rounded bg-teal-700 hover:bg-teal-600 text-white text-sm disabled:opacity-50"
          >
            {phase === "running" ? "Läuft…" : "Neu untersuchen"}
          </button>
        </div>
      </header>

      <main className="max-w-3xl mx-auto p-6 space-y-5">
        {(phase === "running" || phase === "idle") && (
          <div data-testid="running" className="text-gray-400 text-sm py-16 text-center">
            Untersuchung läuft – die Freigabe erscheint, sobald der Agent am Freigabeknoten hält…
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-wein-600 bg-wein-700/20 p-3 text-wein-500 text-xs">
            {error}
          </div>
        )}

        {(phase === "interrupt" || phase === "approving" || phase === "done") && payload && (
          <>
            {/* Beste Hypothese mit großem Konfidenzwert und Schwellenlinie */}
            <section
              data-testid="best-hypothesis"
              className="rounded-xl border border-gray-700 bg-gray-900 p-5"
            >
              <p className="text-[11px] uppercase tracking-wide text-gray-500 mb-1">
                Beste Hypothese
              </p>
              <div className="flex items-end justify-between gap-4">
                <div>
                  <p className="text-2xl font-semibold text-gray-100">{reason}</p>
                  {payload.hypothesis?.cause && (
                    <p className="text-xs text-gray-400 mt-1 max-w-md">{payload.hypothesis.cause}</p>
                  )}
                </div>
                <div className="text-right">
                  <p
                    data-testid="hypo-confidence"
                    className={[
                      "text-4xl font-bold tabular-nums",
                      hypoConf >= threshold ? "text-salbei-500" : "text-amber-400",
                    ].join(" ")}
                  >
                    {pct(hypoConf)}
                  </p>
                  <p className="text-[10px] text-gray-500">Konfidenz</p>
                </div>
              </div>
              <div className="mt-4">
                <ConfidenceBar confidence={hypoConf} threshold={threshold} />
                <p data-testid="threshold-line" className="text-[11px] text-gray-500 mt-1">
                  Aktive Konfidenzschwelle: <span className="text-wein-500">{pct(threshold)}</span>{" "}
                  (zur Laufzeit aus der Konfiguration gelesen)
                </p>
              </div>
            </section>

            {/* Empfohlene Maßnahmen */}
            <section className="space-y-3">
              <p className="text-wein-500 text-xs font-semibold uppercase tracking-wide">
                Freigabe erforderlich – der Agent empfiehlt, er führt nicht aus
              </p>
              {recommended.length === 0 && (
                <p className="text-gray-500 text-sm">Keine Maßnahme über der Schwelle.</p>
              )}
              {recommended.map((a, i) => {
                const jr = judgeByTitle(a.title);
                return (
                  <div
                    key={i}
                    data-testid="action-card"
                    className="rounded-lg border border-gray-700 bg-gray-900 p-4 space-y-2"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-gray-100 text-sm font-medium">{a.title}</p>
                      <PolicyBadge level={a.level} />
                    </div>
                    {a.description && <p className="text-xs text-gray-400">{a.description}</p>}
                    <ConfidenceBar confidence={a.confidence ?? 0} threshold={threshold} />
                    <Belegtext action={a} />
                    {jr && (
                      <p
                        className={[
                          "text-[11px]",
                          jr.verified ? "text-salbei-500" : "text-wein-500",
                        ].join(" ")}
                      >
                        {jr.verified ? "✓ vom Judge bestätigt" : `✗ Judge: ${jr.judge_note}`}
                      </p>
                    )}
                  </div>
                );
              })}
            </section>

            {/* Hypothesen/Maßnahmen unter der Schwelle – sichtbar, nicht versteckt */}
            {below.length > 0 && (
              <section data-testid="below-threshold" className="space-y-3">
                <p className="text-amber-400 text-xs font-semibold uppercase tracking-wide">
                  Unter der Schwelle – zur Kenntnis, nicht empfohlen
                </p>
                {below.map((a, i) => (
                  <div
                    key={i}
                    data-testid="below-card"
                    className="rounded-lg border border-amber-500/40 bg-amber-500/5 p-4 space-y-2"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-gray-200 text-sm font-medium">{a.title}</p>
                      <PolicyBadge level={a.level} />
                    </div>
                    <p className="text-[11px] text-amber-400">
                      Konfidenz {pct(a.confidence ?? 0)} unter Schwelle {pct(threshold)} – zur
                      Kenntnis, nicht empfohlen.
                    </p>
                    {a.description && <p className="text-xs text-gray-400">{a.description}</p>}
                    <ConfidenceBar confidence={a.confidence ?? 0} threshold={threshold} />
                    <Belegtext action={a} />
                  </div>
                ))}
              </section>
            )}

            {/* Entscheidung */}
            {phase !== "done" && (
              <section className="rounded-lg border border-gray-700 bg-gray-900 p-4 space-y-3">
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
                    disabled={phase === "approving"}
                    className="px-4 py-1.5 rounded bg-teal-700 hover:bg-teal-600 text-white text-sm disabled:opacity-50"
                  >
                    Freigeben
                  </button>
                  <button
                    onClick={() => decide(false)}
                    disabled={phase === "approving"}
                    className="px-4 py-1.5 rounded bg-wein-600 hover:bg-wein-500 text-white text-sm disabled:opacity-50"
                  >
                    Ablehnen
                  </button>
                </div>
              </section>
            )}

            {phase === "done" && approved !== null && (
              <section
                data-testid="approval-result"
                className={[
                  "rounded-lg border p-4 text-sm font-semibold",
                  approved
                    ? "border-teal-600 bg-teal-700/15 text-teal-400"
                    : "border-wein-600 bg-wein-700/15 text-wein-500",
                ].join(" ")}
              >
                {approved
                  ? "Freigegeben – regulärer Abschluss (rollenbasiert im Audit protokolliert)."
                  : "Abgelehnt – sauberer Abbruch, kein Maßnahmen-Abschluss (im Audit protokolliert)."}
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}
