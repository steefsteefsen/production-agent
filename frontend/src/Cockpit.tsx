import { useEffect, useRef, useState } from "react";
import "./cockpit.css";

/**
 * Sechs-Tab-Cockpit (Bediener, Live-Daten, MCP, Wissen/RAG, Sicherheit, Konfiguration).
 * Struktur/Stil 1:1 aus ui_mockup_tabs.html; alle Daten kommen real aus der API (kein Fake).
 */

const TABS = [
  { id: "operator", label: "Bediener", operator: true },
  { id: "live", label: "Live-Daten" },
  { id: "mcp", label: "MCP" },
  { id: "rag", label: "Wissen / RAG" },
  { id: "security", label: "Sicherheit" },
  { id: "config", label: "Konfiguration" },
] as const;
type TabId = (typeof TABS)[number]["id"];

const pct = (x: number) => `${Math.round(x * 100)}%`;

async function getJSON<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}
async function postJSON<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// ===================================================================== BEDIENER
interface Hyp {
  reason_code?: string;
  cause?: string;
  confidence?: number;
}
interface Action {
  title?: string;
  description?: string;
  level?: string;
  confidence?: number;
  beleg_text?: string;
  beleg_quelle?: string;
  rationale?: string;
}
interface Judge {
  title: string;
  verified: boolean;
  judge_note: string;
}
interface Impact {
  cost_eur?: number;
  lost_units?: number;
  expected_downtime_min?: number;
  orders_at_risk?: string[];
  orders?: { order_id: string }[];
}
interface Payload {
  hypotheses?: Hyp[];
  hypothesis?: Hyp;
  actions?: Action[];
  applied_threshold?: number | null;
  judge_results?: Judge[];
  impact?: Impact;
}

/** Explizite „keine Aussage möglich"-Anzeige statt stillschweigend leer (ehrliche Grenze). */
function NoData({ text }: { text: string }) {
  return (
    <span className="no-data" data-testid="no-data">
      {text}
    </span>
  );
}

// Bekannte Demo-Fälle (Finding B). Jeder Fall = eigener Thread-Zustand.
const EVENTS = [
  { id: 360, label: "360 · STO-FOLIE" },
  { id: 336, label: "336 · STO-ANTRIEB" },
];
type OpPhase = "running" | "interrupt" | "done" | "error";
interface OpRun {
  thread_id: string | null;
  phase: OpPhase;
  approved: boolean | null;
  payload: Payload | null;
  ingested: string | null;
}
// Modul-Store: überlebt Tab-Wechsel (Unmount/Remount), je Ereignis ein unabhängiger Zustand.
// Der Checkpointer im Backend bleibt Quelle der Wahrheit (GET /investigations/{thread}/state).
const opRuns: Record<number, OpRun> = {};

function OperatorTab() {
  const [eventId, setEventId] = useState<number>(EVENTS[0].id);
  const [phase, setPhase] = useState<OpPhase>("running");
  const [meta, setMeta] = useState<{ thread_id: string; event_id: number | null } | null>(null);
  const [payload, setPayload] = useState<Payload | null>(null);
  const [raw, setRaw] = useState("");
  const [fbStep, setFbStep] = useState<1 | 2>(1);
  const [suggested, setSuggested] = useState("");
  const [ingested, setIngested] = useState<string | null>(null);
  const [approved, setApproved] = useState<boolean | null>(null);
  const [restored, setRestored] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const esRef = useRef<EventSource | null>(null);
  const phaseRef = useRef(phase);
  const setP = (p: OpPhase) => {
    phaseRef.current = p;
    setPhase(p);
  };
  const persist = (patch: Partial<OpRun>) => {
    opRuns[eventId] = { ...(opRuns[eventId] ?? ({} as OpRun)), ...patch };
  };

  const start = (evId: number) => {
    esRef.current?.close();
    setMeta(null);
    setPayload(null);
    setRaw("");
    setFbStep(1);
    setSuggested("");
    setIngested(null);
    setApproved(null);
    setRestored(false);
    setErr("");
    setP("running");
    const es = new EventSource(`/investigations/stream?line_id=L1&event_id=${evId}`);
    esRef.current = es;
    es.addEventListener("start", (e) => {
      const m = JSON.parse((e as MessageEvent).data);
      setMeta(m);
      persist({ thread_id: m.thread_id, phase: "running", approved: null, ingested: null });
    });
    es.addEventListener("interrupt", (e) => {
      const pl = JSON.parse((e as MessageEvent).data).payload ?? {};
      setPayload(pl);
      setP("interrupt");
      persist({ phase: "interrupt", payload: pl });
      es.close();
    });
    es.onerror = () => {
      es.close();
      if (phaseRef.current !== "interrupt" && phaseRef.current !== "done") {
        setErr("SSE-Verbindung abgebrochen.");
        setP("error");
      }
    };
  };

  // Finding A: bei (Re-)Mount und Ereigniswechsel den Ist-Zustand des Threads abfragen, NICHT
  // blind neu starten. Nur wenn kein Zustand existiert, eine neue Untersuchung anstoßen.
  useEffect(() => {
    let cancelled = false;
    const restore = async () => {
      const known = opRuns[eventId];
      if (known?.thread_id) {
        try {
          const s = await getJSON<{
            status: string;
            payload?: Payload;
            approved?: boolean;
          }>(`/investigations/${known.thread_id}/state`);
          if (cancelled) return;
          if (s.status === "interrupt" || s.status === "done") {
            setMeta({ thread_id: known.thread_id, event_id: eventId });
            setPayload(s.payload ?? known.payload ?? null);
            setIngested(known.ingested ?? null);
            if (s.status === "done") {
              setApproved(s.approved ?? known.approved ?? null);
              setP("done");
            } else {
              setP("interrupt");
            }
            setRestored(true);
            return;
          }
        } catch {
          /* Zustand nicht abrufbar → neu starten */
        }
      }
      start(eventId);
    };
    restore();
    return () => {
      cancelled = true;
      esRef.current?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventId]);

  const suggest = async () => {
    setBusy(true);
    setErr("");
    try {
      const d = await postJSON<{ suggestion: string }>("/investigations/feedback/suggest", {
        raw: raw.trim() || "Rolle neu eingespannt, nachjustiert",
        reason_code: payload?.hypothesis?.reason_code ?? "",
      });
      setSuggested(d.suggestion);
      setFbStep(2);
    } catch (e) {
      setErr(`Vervollständigung fehlgeschlagen: ${e}`);
    } finally {
      setBusy(false);
    }
  };
  const accept = async () => {
    setBusy(true);
    setErr("");
    try {
      await postJSON("/knowledge/documents", { text: suggested });
      setIngested(suggested);
      persist({ ingested: suggested });
    } catch (e) {
      setErr(`Einspeisen fehlgeschlagen: ${e}`);
    } finally {
      setBusy(false);
    }
  };
  const decide = async (ok: boolean) => {
    if (!meta) return;
    setBusy(true);
    try {
      await postJSON("/investigations/approve", {
        thread_id: meta.thread_id,
        approved: ok,
        comment: ingested ? "Rückkopplung freigegeben" : "",
        approved_action_titles: [],
        event_id: meta.event_id,
      });
      setApproved(ok);
      setP("done");
      persist({ phase: "done", approved: ok });
    } catch (e) {
      setErr(`Freigabe fehlgeschlagen: ${e}`);
    } finally {
      setBusy(false);
    }
  };

  const thr = typeof payload?.applied_threshold === "number" ? payload.applied_threshold : 0.6;
  const hyps = payload?.hypotheses?.length
    ? payload.hypotheses
    : payload?.hypothesis
      ? [payload.hypothesis]
      : [];
  const actions = payload?.actions ?? [];
  const judge = payload?.judge_results ?? [];
  const nApproval = actions.filter((a) => a.level === "approval_required").length;

  const header = (
    <div className="op-header op-header-row">
      <div>
        <div className="op-title">Untersuchung — Ereignis #{eventId}</div>
        <div className="op-sub">
          Replay-Uhr aktiv · Agent empfiehlt, er führt nicht aus
          {restored && <span data-testid="op-restored"> · Zustand wiederhergestellt</span>}
        </div>
      </div>
      <div className="op-eventsel">
        <label>Ereignis</label>
        <select
          data-testid="event-select"
          value={eventId}
          onChange={(e) => setEventId(Number(e.target.value))}
        >
          {EVENTS.map((ev) => (
            <option key={ev.id} value={ev.id}>
              {ev.label}
            </option>
          ))}
        </select>
        <button
          className="op-btn-sm"
          data-testid="op-restart"
          disabled={phase === "running"}
          onClick={() => start(eventId)}
        >
          Neu untersuchen
        </button>
      </div>
    </div>
  );

  if (phase === "running")
    return (
      <div data-testid="operator-tab">
        {header}
        <div data-testid="op-running" className="muted">
          Untersuchung läuft – die Freigabe erscheint, sobald der Agent am Freigabeknoten hält…
        </div>
      </div>
    );
  if (phase === "error")
    return (
      <div data-testid="operator-tab">
        {header}
        <div className="cfg-drift">{err}</div>
      </div>
    );

  return (
    <div data-testid="operator-tab">
      {header}

      {phase === "done" ? (
        <div
          className={`op-status ${approved ? "done-approved" : "done-rejected"}`}
          data-testid="op-status-done"
        >
          <span className="badge">{approved ? "FREIGEGEBEN" : "ABGELEHNT"}</span>
          <div className="txt">
            <b>
              {approved
                ? "Maßnahmen freigegeben — regulärer Abschluss"
                : "Maßnahmen abgelehnt — sauberer Abbruch, kein Abschluss"}
            </b>
            <span>
              {hyps[0]?.reason_code ?? "—"} · rollenbasiert im Audit protokolliert
            </span>
          </div>
        </div>
      ) : (
        <div className="op-status" data-testid="op-status">
          <span className="badge">STÖRUNG</span>
          <div className="txt">
            <b>{hyps[0]?.reason_code ?? "—"} · beste Hypothese</b>
            <span>{hyps[0]?.cause ?? ""}</span>
          </div>
        </div>
      )}

      <div className="op-hero" data-testid="op-hero">
        <div className="op-hero-h">URSACHENHYPOTHESEN — ALLE KANDIDATEN, NICHT NUR DIE BESTE</div>
        {hyps.map((h, i) => {
          const v = h.confidence ?? 0;
          const best = i === 0 && v >= thr;
          return (
            <div className="hyp-row" data-testid="hyp-row" key={i}>
              <div className="hyp-label">
                <div className="n">
                  {h.reason_code} — {h.cause}
                </div>
                <div className="r">{i === 0 ? "beste Hypothese" : "Alternative"}</div>
              </div>
              <div className="hyp-chart">
                <div className="hyp-bar-track">
                  <div
                    className={`hyp-bar-fill ${best ? "best" : "alt"}`}
                    style={{ width: pct(v) }}
                  />
                  <div
                    className="hyp-threshold"
                    data-testid="hyp-threshold"
                    style={{ left: pct(thr) }}
                  />
                </div>
              </div>
              <div className={`hyp-val ${best ? "best" : "alt"}`}>{v.toFixed(2)}</div>
            </div>
          );
        })}
        <div className="hyp-legend">
          <span>
            <span className="sw" style={{ background: "var(--green)" }} />
            über Schwelle → empfohlen
          </span>
          <span>
            <span className="sw" style={{ background: "var(--dimmer)" }} />
            unter Schwelle → nur zur Kenntnis
          </span>
          <span>
            <span className="sw" style={{ background: "var(--amber)", width: 2, height: 12 }} />
            Schwelle {thr.toFixed(2)}
          </span>
        </div>
      </div>

      <div className="op-actions-h">
        MASSNAHMEN ZUR BESTEN HYPOTHESE — {actions.length}, DAVON {nApproval} FREIGABEPFLICHTIG
      </div>
      {actions.map((a, i) => {
        const jr = judge.find((j) => j.title === a.title);
        const inform = a.level === "inform";
        return (
          <div className="op-action" data-testid="op-action" key={i}>
            <div className="op-action-top">
              <span
                className={`op-badge ${inform ? "inform" : "approval"}`}
                data-testid="policy-badge"
                data-level={a.level}
              >
                {inform ? "inform" : "approval_required"}
              </span>
              <span className="op-action-title">{a.title}</span>
            </div>
            {a.description && <div className="op-action-desc">{a.description}</div>}
            {a.beleg_text ? (
              <div className="op-quote" data-testid="belegtext">
                „{a.beleg_text}"
                <span className="src">Original-Zitat · {a.beleg_quelle}</span>
              </div>
            ) : (
              a.rationale && <div className="op-action-desc">Beleg: {a.rationale}</div>
            )}
            {jr && (
              <div className={`op-judge ${jr.verified ? "" : "fail"}`}>
                {jr.verified ? "✓ vom Judge bestätigt" : `✗ Judge: ${jr.judge_note}`}
              </div>
            )}
          </div>
        );
      })}

      {/* Wirkung (business_rules) – explizite Anzeige, wenn nichts ableitbar ist */}
      <div className="op-actions-h">WIRKUNG (DETERMINISTISCHE REGEL, KEIN MODELL)</div>
      <div className="op-action" data-testid="impact-box">
        {payload?.impact && typeof payload.impact.cost_eur === "number" ? (
          <>
            <div className="op-action-desc">
              Stillstandskosten: <b>{Math.round(payload.impact.cost_eur)} €</b> ·{" "}
              {payload.impact.lost_units ?? 0} Einheiten Verlust ·{" "}
              {payload.impact.expected_downtime_min ?? "?"} min Stillstand
            </div>
            {payload.impact.orders_at_risk && payload.impact.orders_at_risk.length > 0 ? (
              <div className="op-action-desc" data-testid="orders-at-risk">
                Gefährdete Aufträge: {payload.impact.orders_at_risk.join(", ")}
              </div>
            ) : (
              <NoData text="Keine Leistungsdaten ableitbar — kein Auftrag im gefährdeten Bereich (außerhalb des heutigen Modellumfangs)." />
            )}
          </>
        ) : (
          <NoData text="Keine Wirkungsschätzung verfügbar — außerhalb des heutigen Modellumfangs." />
        )}
      </div>

      {/* Rückkopplung mit LLM-Vervollständigung (zwei getrennte Freigabe-Schritte) */}
      {phase === "interrupt" && (
        <div className="op-decision-wrap">
          {fbStep === 1 && !ingested && (
            <div className="op-fb-step" data-testid="fb-step-1">
              <label>WAS HAT DEN WIEDERANLAUF TATSÄCHLICH ERMÖGLICHT? (bei Freigabe verpflichtend)</label>
              <textarea
                data-testid="fb-raw"
                value={raw}
                onChange={(e) => setRaw(e.target.value)}
                placeholder={'z. B. „Rolle neu eingespannt, nachjustiert" — auch stichwortartig reicht.'}
              />
              <div className="hint">
                Ein Sprachmodell (Haiku) hilft, daraus einen vollständigen Eintrag zu machen — Sie
                geben das Ergebnis frei, bevor es gespeichert wird.
              </div>
              <button className="op-btn-sm" data-testid="fb-suggest" disabled={busy} onClick={suggest}>
                {busy ? "…" : "Vervollständigung vorschlagen (Haiku)"}
              </button>
            </div>
          )}
          {fbStep === 2 && !ingested && (
            <div className="op-fb-step" data-testid="fb-step-2">
              <div className="fb-compare">
                <div>
                  <div className="fb-col-h">IHRE EINGABE</div>
                  <div className="fb-raw-echo" data-testid="fb-raw-echo">
                    {raw.trim() || "Rolle neu eingespannt, nachjustiert"}
                  </div>
                </div>
                <div>
                  <div className="fb-col-h">
                    VORSCHLAG · HAIKU <span className="fb-tag">zur Freigabe</span>
                  </div>
                  <textarea
                    className="fb-suggested-edit"
                    data-testid="fb-suggested"
                    value={suggested}
                    onChange={(e) => setSuggested(e.target.value)}
                  />
                </div>
              </div>
              <div className="fb-approve-row">
                <button className="op-btn-sm ghost" onClick={() => setFbStep(1)}>
                  Zurück, eigene Formulierung nutzen
                </button>
                <button className="op-btn-sm accept" data-testid="fb-accept" disabled={busy} onClick={accept}>
                  Vorschlag übernehmen &amp; freigeben
                </button>
              </div>
            </div>
          )}
          {ingested && (
            <div className="op-feedback-note" data-testid="fb-note">
              <b>✓ Für den Wissensbestand freigegeben</b>
              {ingested}
            </div>
          )}
        </div>
      )}

      <div className="op-decision">
        {phase === "done" ? (
          <div className="op-feedback-note" data-testid="op-result">
            <b>{approved ? "✓ Freigegeben — regulärer Abschluss" : "✗ Abgelehnt — sauberer Abbruch"}</b>
            Rollenbasiert im Audit protokolliert.
          </div>
        ) : (
          <div className="op-btns">
            <button className="op-btn approve" data-testid="op-approve" disabled={busy} onClick={() => decide(true)}>
              Freigeben
            </button>
            <button className="op-btn reject" disabled={busy} onClick={() => decide(false)}>
              Ablehnen
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ===================================================================== LIVE-DATEN
interface Equip {
  equipment_id: string;
  name: string;
  packml_state?: string | null;
}
interface Order {
  order_id: string;
  product: string;
  planned_qty: number;
  produced_qty: number;
}
function stateClass(s?: string | null): string {
  if (!s) return "idle";
  if (["Held", "Aborted", "Stopped", "Suspended"].includes(s)) return "fault";
  if (s === "Execute") return "ok";
  return "idle";
}
interface Event {
  first_alarm_code?: string;
  reason_code?: string;
  start_ts?: string;
  alarm_count?: number;
}
function LiveTab() {
  const [line, setLine] = useState<{ equipment: Equip[]; orders: Order[] } | null>(null);
  const [alarms, setAlarms] = useState<Event[]>([]);
  const [err, setErr] = useState("");
  useEffect(() => {
    getJSON<{ equipment: Equip[]; orders: Order[] }>("/mes/line/L1").then(setLine).catch((e) => setErr(String(e)));
    getJSON<Event[]>("/mes/events?line_id=L1&limit=10")
      .then((r) => setAlarms((Array.isArray(r) ? r : []).slice(0, 10)))
      .catch(() => setAlarms([]));
  }, []);
  return (
    <div data-testid="live-tab">
      <div className="log-header">
        <div className="log-title">Live-Daten — Linie L1</div>
        <div className="log-note">direkt aus dem simulierten MES, ungefiltert</div>
      </div>
      <div className="dummy-box">
        <span className="ic">💡</span>
        <div>
          <b>Was ist das?</b> Die Rohdaten aus der Anlagensteuerung — bevor der Agent sie
          interpretiert. Kein Vorschlag, keine Bewertung, nur der aktuelle Zustand.
        </div>
      </div>
      {err && <div className="cfg-drift">{err}</div>}
      <div className="section-h">BETRIEBSMITTEL (PACKML)</div>
      <div className="server-grid" style={{ gridTemplateColumns: "repeat(4,1fr)" }}>
        {(line?.equipment ?? []).map((e) => {
          const c = stateClass(e.packml_state);
          return (
            <div className={`live-station ${c === "fault" ? "fault" : ""}`} data-testid="live-station" key={e.equipment_id}>
              <div className="ls-name">{e.name}</div>
              <div className={`ls-state ${c}`}>{e.packml_state ?? "—"}</div>
            </div>
          );
        })}
      </div>
      <div className="section-h">AKTIVE AUFTRÄGE</div>
      <div className="doc-list">
        {(line?.orders ?? []).map((o) => (
          <div className="doc-item" key={o.order_id}>
            <span className="ic">{o.order_id}</span>
            <span className="n">{o.product}</span>
            <span className="c">
              {o.produced_qty} / {o.planned_qty} St
            </span>
          </div>
        ))}
        {!line?.orders?.length && <div className="doc-item">Keine offenen Aufträge.</div>}
      </div>
      <div className="section-h">STÖRUNGSSTROM (LETZTE 10 EREIGNISSE)</div>
      {alarms.map((a, i) => (
        <div className="log-entry" data-testid="alarm-entry" key={i}>
          <div className="log-line1">
            <span className="log-tag block">{a.first_alarm_code ?? "—"}</span>
            <span className="log-server">
              {a.reason_code} · {a.alarm_count ?? 0} Alarme
            </span>
            <span className="log-time">{a.start_ts}</span>
          </div>
        </div>
      ))}
      {!alarms.length && <div className="muted">Kein Störungsstrom abrufbar.</div>}
    </div>
  );
}

// ===================================================================== MCP
interface ToolDef {
  name: string;
  desc: string;
}
interface ServerDef {
  name: string;
  desc: string;
  tools: ToolDef[];
}
interface ToolCall {
  ts: string;
  server: string;
  tool: string;
  params: Record<string, unknown>;
  raw: Record<string, unknown>;
}
// Feste Graph-Knotenreihenfolge; Werkzeugschritte werden mit echten Aufrufen (/observability)
// angereichert. kind → Server/Farbe: mes(grün), knowledge(blau), rules=business_rules(amber),
// llm(lila, kein MCP), gold(Abschluss). Texte spiegeln die STRUKTURELLE LINEARITÄT wider (keine
// Graph-Verzweigung — grep-bestätigt: kein add_conditional_edges).
type StepKind = "mes" | "knowledge" | "rules" | "llm" | "gold";
interface StepDef {
  step: string;
  title: string;
  kind: StepKind;
  server?: string;
  tool?: string;
  desc: string;
}
const TIMELINE: StepDef[] = [
  { step: "0", title: "Alarme normalisieren (Bronze→Silber)", kind: "mes", server: "mes", tool: "get_active_alarms", desc: "Rohalarme werden bereinigt und PackML-Zuständen zugeordnet (alarms_silver) — passiert in der Pipeline vor der Untersuchung, nicht als Agentenschritt." },
  { step: "1", title: "Status & Plan abrufen", kind: "mes", server: "mes", tool: "get_line_status", desc: "Liest aktuellen PackML-Zustand und laufenden Auftrag — reine Simulation, kein Modell beteiligt." },
  { step: "2", title: "Alarme prüfen, Flut erkennen", kind: "mes", server: "mes", tool: "get_active_alarms", desc: "Alarmfenster der letzten 30 Minuten, Schwellenwert nach ISA-18.2." },
  { step: "3a", title: "Wartungsdokumente durchsuchen", kind: "knowledge", server: "knowledge", tool: "search_documents", desc: "BM25 + Vektor, RRF-fusioniert — Textsuche über den Dokumentenbestand." },
  { step: "3b", title: "Ähnliche Vorfälle finden", kind: "knowledge", server: "knowledge", tool: "search_incidents", desc: "Case-Based Reasoning — strukturierte Suche nach Alarmcode/PackML-Zustand." },
  { step: "4", title: "Ursachenhypothese bilden", kind: "llm", desc: "Sonnet 5 — kein Werkzeugaufruf, reine Modellinferenz über den gesammelten Kontext." },
  { step: "5", title: "Wirkung schätzen", kind: "rules", server: "business_rules", tool: "estimate_impact", desc: "Deterministische Geschäftsregel — Nennleistung × Dauer, Kostensatz aus Stammdaten, kein Modell." },
  { step: "6", title: "Maßnahmen ableiten", kind: "llm", desc: "Sonnet 5, Beleg-Pflicht je Maßnahme. Die Konfidenzschwelle klassifiziert danach — Entscheidungslogik INNERHALB dieses Knotens, KEINE Graph-Verzweigung (grep: kein add_conditional_edges, der Graph ist strukturell linear)." },
  { step: "7", title: "Beleg-Prüfung", kind: "llm", desc: "Haiku 4.5, eigener Kontext ohne Knoten-4/6-Historie — unabhängige Gegenprüfung. Das Ergebnis wird angezeigt, verzweigt NICHT (kein Auto-Verwerfen)." },
  { step: "8", title: "Freigabe-Gate", kind: "llm", desc: "Der Graph hält an (interrupt) — der Mensch entscheidet außerhalb des Graphen. Freigeben/Ablehnen ist keine kodierte Verzweigung, sondern Checkpointer-Resume mit unterschiedlichem Eingabewert; der Graph bleibt linear." },
  { step: "G", title: "Echtes Gold — nur im Agentenzustand", kind: "gold", desc: "KEINE neue Zeile in downtime_events_gold (diese Tabelle existierte schon vor dem Lauf als Alarm-Aggregation). Die echte Gold-Veredelung — Ursache MIT Maßnahme fusioniert — entsteht hier im Zustand des Agenten und wird bei Freigabe als Rückkopplung in den Wissensbestand (Quelle rueckkopplung) geschrieben, NICHT in downtime_events_gold." },
];

function McpTab() {
  const [servers, setServers] = useState<ServerDef[]>([]);
  const [calls, setCalls] = useState<ToolCall[]>([]);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  useEffect(() => {
    getJSON<{ servers: ServerDef[] }>("/mcp/servers").then((d) => setServers(d.servers)).catch(() => {});
    getJSON<{ tools: ToolCall[] }>("/observability").then((d) => setCalls(d.tools)).catch(() => {});
  }, []);
  const callFor = (s: StepDef) =>
    s.tool ? calls.find((c) => c.server === s.server && c.tool === s.tool) : undefined;
  return (
    <div data-testid="mcp-tab">
      <div className="log-header">
        <div className="log-title">MCP — Ablauf dieses Laufs</div>
        <div className="log-note">vertikale Timeline · welcher Schritt greift auf welchen Server zu</div>
      </div>
      <div className="dummy-box">
        <span className="ic">💡</span>
        <div>
          <b>Was ist MCP?</b> Ein offenes Protokoll, über das der Agent mit klar abgegrenzten
          Werkzeugen spricht — statt direkt auf Datenbanken zuzugreifen. Jeder Schritt zeigt, welcher
          Server angesprochen wurde. Klicken für Details.
        </div>
      </div>
      <div className="section-h">SERVER IN DIESEM SYSTEM</div>
      <div className="server-grid">
        {servers.map((s) => (
          <div className="server-card" data-testid="server-card" key={s.name}>
            <div className="name">{s.name}</div>
            <div className="desc">{s.desc}</div>
            {s.tools.map((t) => (
              <div className="tool" key={t.name}>
                <span className="tn">{t.name}</span>
                <span className="td">{t.desc}</span>
              </div>
            ))}
          </div>
        ))}
      </div>
      <div className="tl-legend">
        <span><span className="sw" style={{ background: "var(--green)" }} />mes — Live-Simulation</span>
        <span><span className="sw" style={{ background: "var(--blue)" }} />knowledge — RAG + Fallsuche</span>
        <span><span className="sw" style={{ background: "var(--amber)" }} />business_rules — deterministisch</span>
        <span><span className="sw" style={{ background: "var(--purple)" }} />Sprachmodell — kein MCP</span>
      </div>
      <div className="timeline" data-testid="mcp-timeline">
        {TIMELINE.map((s) => {
          const c = callFor(s);
          const isOpen = !!open[s.step];
          const nomcp = s.kind === "llm";
          const dot = s.kind === "rules" ? "rules" : s.kind;
          return (
            <div className="tnode" key={s.step}>
              <div className={`tnode-dot ${dot}`}>{s.step}</div>
              <div
                className={`tnode-card ${isOpen ? "open" : ""}`}
                data-testid="mcp-step"
                onClick={() => setOpen((o) => ({ ...o, [s.step]: !o[s.step] }))}
              >
                <div className="tnode-head">
                  <div className="tnode-step">Schritt {s.step}</div>
                  <div className="tnode-title">{s.title}</div>
                  <div className={`tnode-server ${nomcp ? "llm" : dot}`}>
                    {nomcp ? "kein MCP" : s.server}
                  </div>
                  <span className="tnode-chevron">{isOpen ? "▾" : "▸"}</span>
                </div>
                {isOpen && (
                  <div className="tnode-body-inner">
                    <div className="tnode-desc">{s.desc}</div>
                    {c ? (
                      <>
                        <div className="tnode-kv">
                          <span className="k">call:</span> {c.server}.{c.tool}{" "}
                          <span className="k">· {c.ts}</span>
                        </div>
                        <div className="tnode-kv">
                          <span className="k">params:</span> {JSON.stringify(c.params)}
                        </div>
                        <div className="tnode-raw">{JSON.stringify(c.raw)}</div>
                      </>
                    ) : nomcp ? (
                      <div className="tnode-nomcp">Reine Modellinferenz — kein Werkzeugaufruf.</div>
                    ) : s.kind === "gold" ? (
                      <div className="tnode-nomcp">
                        Zustand am Laufende; bei Freigabe → Einspeisung in den Wissensbestand
                        (Quelle rueckkopplung).
                      </div>
                    ) : (
                      <div className="tnode-nomcp">Kein Aufruf in diesem Lauf erfasst.</div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {!calls.length && (
        <div className="muted">Noch kein Lauf — im Bediener-Tab eine Untersuchung starten.</div>
      )}
    </div>
  );
}

// ===================================================================== RAG
interface Hit {
  doc: string;
  chunk_id: string;
  text: string;
  rrf_rank: number;
  bm25_rank?: number | null;
  vec_rank?: number | null;
}
/** Kurzform einer Chunk-Kennung (Finding C): "MA-04#37" → "Chunk 37". */
function chunkLabel(h: Hit): string {
  const n = (h.chunk_id || "").split("#")[1];
  return n ? `Chunk ${n}` : h.chunk_id || "Chunk";
}
/** Erste ~80 Zeichen des Chunk-Textes, damit zwei Chunks desselben Dokuments unterscheidbar sind. */
function snippet(h: Hit): string {
  const t = (h.text || "").replace(/\s+/g, " ").trim();
  return t.length > 80 ? t.slice(0, 80) + "…" : t;
}
// Ampel: on = per grep real aktiv genutzt (nur ISA-18.2); ctx = in decisions.yaml/ADRs referenziert;
// off = bewusst ausgeschlossen (Begründung aus action_policy). KEIN HACCP – nirgends referenziert.
const NORMS = [
  {
    state: "on",
    label: "aktiv genutzt",
    title: "ISA-18.2 — Alarm Management",
    desc: "Definiert die Alarmflut-Schwelle (≥10 Alarme/10 Min), die die Alarmfluterkennung tatsächlich anwendet.",
  },
  {
    state: "ctx",
    label: "Kontext",
    title: "EEMUA 191 — Alarm Systems",
    desc: "Ergänzender Referenzrahmen zur Alarmbewirtschaftung, gemeinsam mit ISA-18.2 in decisions.yaml genannt.",
  },
  {
    state: "ctx",
    label: "Kontext",
    title: "ISO 22400-2 / VDMA 66412 — Kennzahlen & Ereignisdefinition",
    desc: "Grundlage der Störungs-/Ereignisdefinition und Stillstandszeit (ADR-0001).",
  },
  {
    state: "ctx",
    label: "Kontext",
    title: "IEC 62443 — Industrielle Cybersicherheit",
    desc: "Referenzrahmen für OT-Sicherheit — sql_guard/injection_guard folgen dem Grundgedanken, ohne Zertifizierung.",
  },
  {
    state: "off",
    label: "bewusst ausgeschlossen",
    title: "ISO 13849 / IEC 61508 — Funktionale Sicherheit",
    desc: "Bewusst außerhalb: der Agent ist kein sicherheitsgerichteter Teil (action_policy schließt Sicherheitseingriffe aus).",
  },
];
const DOC_GROUPS: { key: string; label: string; live?: boolean; match: (d: string) => boolean }[] = [
  { key: "ma", label: "MASCHINEN-HANDBÜCHER", match: (d) => d.startsWith("MA-") },
  { key: "sb", label: "STÖRUNGSBERICHTE", match: (d) => d.startsWith("SB-") },
  {
    key: "ref",
    label: "REFERENZ",
    match: (d) => /^(BA-|FC-|SDB-|INJ-)/.test(d),
  },
  { key: "live", label: "RÜCKKOPPLUNG · LIVE", live: true, match: (d) => d.startsWith("rueckkopplung") },
];

function RagTab() {
  const [inv, setInv] = useState<{ documents: [string, number][]; total_chunks: number; runtime_count: number } | null>(null);
  const [res, setRes] = useState<{ hits: Hit[]; code_match: boolean; vector_available: boolean } | null>(null);
  useEffect(() => {
    getJSON<typeof inv>("/knowledge/documents").then(setInv).catch(() => {});
    getJSON<{ hits: Hit[]; code_match: boolean; vector_available: boolean }>(
      "/knowledge/search?q=" + encodeURIComponent("Folienbahn läuft schräg Siegelnaht"),
    )
      .then(setRes)
      .catch(() => {});
  }, []);
  const docs = inv?.documents ?? [];
  const maxCount = Math.max(1, ...docs.map(([, n]) => n));
  const hits = res?.hits ?? [];
  const bm25Lane = [...hits]
    .filter((h) => h.bm25_rank != null)
    .sort((a, b) => (a.bm25_rank ?? 99) - (b.bm25_rank ?? 99))
    .slice(0, 4);
  return (
    <div data-testid="rag-tab">
      <div className="log-header">
        <div className="log-title">Wissen / RAG</div>
        <div className="log-note">BM25 + Vektor → RRF</div>
      </div>
      <div className="dummy-box">
        <span className="ic">💡</span>
        <div>
          <b>Was passiert hier?</b> Der Agent durchsucht zwei Quellen gleichzeitig — Stichwortsuche
          (exakte Begriffe wie Fehlercodes) und Bedeutungssuche (Umschreibungen). Beide Ranglisten
          werden fusioniert (RRF), damit weder Zufall noch reine Wortgleichheit allein entscheidet.
        </div>
      </div>

      <div className="section-h">DOKUMENTENBESTAND — {inv?.total_chunks ?? "…"} CHUNKS</div>
      <div className="doc-groups">
        {DOC_GROUPS.map((g) => {
          const items = docs.filter(([d]) => g.match(d));
          return (
            <div className={`doc-group ${g.live ? "live" : ""}`} data-testid="doc-group" key={g.key}>
              <div className="doc-group-h">{g.label}</div>
              {items.map(([d, n]) => (
                <div className="doc-map-item" data-testid="doc-item" key={d}>
                  <div className="doc-map-name">{d}</div>
                  <div className="doc-bar-track">
                    <div className="doc-bar-fill" style={{ width: `${Math.round((n / maxCount) * 100)}%` }} />
                  </div>
                  <div className="doc-map-count">
                    {n} Chunks{g.live ? " — zur Laufzeit vom Bediener eingespeist" : ""}
                  </div>
                </div>
              ))}
              {!items.length && (
                <div className="doc-map-count" data-testid={g.live ? "rag-runtime-empty" : undefined}>
                  {g.live ? "noch keine Einspeisung" : "—"}
                </div>
              )}
            </div>
          );
        })}
      </div>
      {inv && inv.runtime_count > 0 && (
        <div className="muted" data-testid="rag-runtime">
          {inv.runtime_count} Chunk(s) zur Laufzeit über die Bediener-Rückkopplung eingespeist (Quelle
          rueckkopplung, nicht downtime_events_gold).
        </div>
      )}

      <div className="section-h">SUCHLAUF — WIE BM25 UND VEKTOR ZUR FUSIONIERTEN RANGFOLGE WERDEN</div>
      <div className="fusion-card" data-testid="fusion-card">
        <div className="fusion-query">"Folienbahn läuft schräg, Siegelnaht unvollständig"</div>
        <div className="fusion-meta">
          Exakter Fehlercode erkannt: {res?.code_match ? "ja → BM25 doppelt gewichtet" : "nein → gleiche Gewichtung BM25 / Vektor"}
        </div>
        <div className="fusion-lanes">
          <div className="lane bm25">
            <div className="lane-h">BM25 · STICHWORT</div>
            {bm25Lane.map((h, i) => (
              <div className="lane-item" key={i}>
                {h.doc} · {chunkLabel(h)}
              </div>
            ))}
          </div>
          <div className="fuse-arrows">
            →<span className="rrf-badge">RRF</span>→
          </div>
          <div className="lane vec">
            <div className="lane-h">VEKTOR · BEDEUTUNG</div>
            {res?.vector_available ? (
              hits
                .filter((h) => h.vec_rank != null)
                .sort((a, b) => (a.vec_rank ?? 99) - (b.vec_rank ?? 99))
                .slice(0, 4)
                .map((h, i) => (
                  <div className="lane-item" key={i}>
                    {h.doc} · {chunkLabel(h)}
                  </div>
                ))
            ) : (
              <div className="lane-item na" data-testid="vec-na">
                nicht verfügbar — kein Vektor-Index in dieser Umgebung; RRF fusioniert nur BM25
              </div>
            )}
          </div>
        </div>
        <div className="fusion-result">
          <div className="fusion-result-h">FUSIONIERTE RANGFOLGE (RRF) — je Eintrag ein Chunk</div>
          {hits.slice(0, 4).map((h, i) => (
            <div className="result-row" data-testid="rrf-rank" key={i}>
              <div className="result-rank">{h.rrf_rank}</div>
              <div className="result-name" data-testid="rrf-name">
                <span className="rn-doc">
                  {h.doc} · {chunkLabel(h)}
                </span>
                <span className="rn-snip">„{snippet(h)}"</span>
              </div>
              <div className="result-src">
                {h.bm25_rank != null && <span className="src-chip bm25">BM25 #{h.bm25_rank}</span>}
                {h.vec_rank != null && <span className="src-chip vec">Vek #{h.vec_rank}</span>}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="section-h">NORMEN &amp; VORGABEN, DIE DAS VORGEHEN BEEINFLUSSEN</div>
      <div className="norm-list">
        {NORMS.map((n) => (
          <div className={`norm-item ${n.state === "off" ? "excluded" : ""}`} data-testid="norm-item" key={n.title}>
            <span className={`norm-dot ${n.state}`} />
            <div className="t">
              <b>{n.title}</b>
              <span>{n.desc}</span>
            </div>
            <span className={`norm-status ${n.state}`}>{n.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ===================================================================== SICHERHEIT
interface SecEntry {
  ts: string;
  guard: string;
  allowed: boolean;
  detail: string;
}
function SecurityTab() {
  const [sec, setSec] = useState<SecEntry[]>([]);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    getJSON<{ security: SecEntry[] }>("/observability").then((d) => setSec(d.security)).catch(() => {});
  }, []);
  const blocked = sec.filter((s) => !s.allowed).length;
  return (
    <div data-testid="security-tab">
      <div className="log-header">
        <div className="log-title">Sicherheit — Guard-Entscheidungen</div>
        <div className="log-note">sql_guard · injection_guard · judge</div>
      </div>
      <div className="dummy-box">
        <span className="ic">💡</span>
        <div>
          <b>Was ist das?</b> Jeder Datenzugriff und jede Maßnahme läuft durch automatische
          Prüfungen, bevor sie sichtbar wird — unabhängig davon, was das Sprachmodell „möchte". Diese
          Regeln sind fest programmiert, nicht Teil des Modells.
        </div>
      </div>
      <div className="kpi" data-testid="kpi-security" onClick={() => setOpen((o) => !o)}>
        <div>
          <div className="kpi-main">
            {sec.length} Prüfungen · {blocked} blockiert{blocked ? " (erwartet)" : ""}
          </div>
          <div className="kpi-sub">sql_guard · injection_guard · judge — fest programmiert</div>
        </div>
        <span className="kpi-toggle">{open ? "▲ Details verbergen" : "▼ Rohdaten anzeigen"}</span>
      </div>
      {open &&
        sec.map((s, i) => (
          <div className="log-entry" data-testid="sec-entry" key={i}>
            <div className="sec-entry">
              <div className={`sec-icon ${s.allowed ? "allow" : "block"}`}>
                {s.allowed ? "✓" : "✗"}
              </div>
              <div>
                <div className="log-body">
                  <span className="k">{s.guard}</span> — {s.detail}
                </div>
                <div className="log-time">{s.ts}</div>
              </div>
            </div>
          </div>
        ))}
      {open && !sec.length && (
        <div className="muted">Noch keine Guard-Entscheidungen — im Bediener-Tab einen Lauf starten.</div>
      )}
    </div>
  );
}

// ===================================================================== KONFIGURATION
interface Slider {
  value: number;
  default?: number;
  min: number;
  max: number;
  step: number;
}
interface Config {
  konfidenzschwelle: Slider;
  vier_augen_eur: Slider;
  alarmflut: Slider;
  mcp_via_protocol: boolean;
  langfuse: boolean;
  drift: boolean;
}
function ConfigTab() {
  const [cfg, setCfg] = useState<Config | null>(null);
  const [saved, setSaved] = useState("");
  const load = () => getJSON<Config>("/api/config").then(setCfg).catch(() => {});
  useEffect(() => {
    load();
  }, []);
  const save = async (field: string, value: number) => {
    await postPut("/api/config", { field, value });
    setSaved(`${field} = ${value}`);
    load();
  };
  if (!cfg)
    return (
      <div className="muted" data-testid="config-tab">
        Konfiguration lädt…
      </div>
    );
  const row = (label: string, sub: string, s: Slider, field: string, fmt: (v: number) => string) => (
    <div className="cfg-row">
      <div className="l">
        {label}
        <span>{sub}</span>
      </div>
      <div className="cfg-slider">
        <input
          type="range"
          min={s.min}
          max={s.max}
          step={s.step}
          defaultValue={s.value}
          data-testid={`slider-${field}`}
          onChange={(e) => {
            const v = document.getElementById(`v-${field}`);
            if (v) v.textContent = fmt(Number(e.target.value));
          }}
          onMouseUp={(e) => save(field, Number((e.target as HTMLInputElement).value))}
          onKeyUp={(e) => save(field, Number((e.target as HTMLInputElement).value))}
        />
        <span className="v" id={`v-${field}`}>
          {fmt(s.value)}
        </span>
      </div>
    </div>
  );
  return (
    <div data-testid="config-tab">
      <div className="log-header">
        <div className="log-title">Konfiguration</div>
        <div className="log-note">Schwellen wirken sofort · runtime.yaml-Override</div>
      </div>
      <div className="dummy-box">
        <span className="ic">💡</span>
        <div>
          <b>Was ist das?</b> Die Schwellenwerte, die der Agent bei jedem Lauf verwendet — Änderung
          an der Konfidenzschwelle wirkt sofort ohne Neustart.
        </div>
      </div>
      {cfg.drift && (
        <div className="cfg-drift" data-testid="cfg-drift">
          ⚠ Konfigurations-Drift: konfidenz.schwelle_empfehlung = {cfg.konfidenzschwelle.value}{" "}
          (gespeichert) weicht von {cfg.konfidenzschwelle.default} (decisions.yaml) ab
        </div>
      )}
      {saved && <div className="muted" data-testid="cfg-saved">Gespeichert: {saved}</div>}
      <div className="cfg-card">
        <div className="h">SCHWELLENWERTE</div>
        {row(
          "Konfidenzschwelle",
          "ab hier wird eine Maßnahme empfohlen, nicht nur informiert (wirkt zur Laufzeit)",
          cfg.konfidenzschwelle,
          "konfidenz.schwelle_empfehlung",
          (v) => v.toFixed(2),
        )}
        {row(
          "Vier-Augen-Schwelle (€)",
          "ab dieser Wirkung ist eine zweite Freigabe zwingend",
          cfg.vier_augen_eur,
          "freigabe.vier_augen_ab_kosten_eur",
          (v) => String(v),
        )}
        {row(
          "Alarmflut-Schwelle",
          "Alarme je 10-Minuten-Fenster (ISA-18.2)",
          cfg.alarmflut,
          "ereignis.alarmflut_alarme",
          (v) => String(v),
        )}
      </div>
      <div className="cfg-card">
        <div className="h">SYSTEMZUSTAND (beim Start gesetzt, zur Laufzeit nicht änderbar)</div>
        <div className="cfg-row">
          <div className="l">
            MCP-Protokollpfad
            <span>Wird beim Start gesetzt (MCP_VIA_PROTOCOL), zur Laufzeit nicht änderbar.</span>
          </div>
          <span
            className="cfg-status"
            data-testid="status-mcp"
            title="Wird beim Start gesetzt (MCP_VIA_PROTOCOL), zur Laufzeit nicht änderbar."
          >
            {cfg.mcp_via_protocol ? "Protokoll (stdio)" : "In-Process"}
          </span>
        </div>
        <div className="cfg-row">
          <div className="l">
            Langfuse-Tracing
            <span>Wird beim Start aus den Umgebungsvariablen gesetzt; zur Laufzeit nicht änderbar.</span>
          </div>
          <span className="cfg-status" data-testid="status-langfuse">
            {cfg.langfuse ? "aktiv" : "inaktiv"}
          </span>
        </div>
      </div>
    </div>
  );
}
async function postPut(url: string, body: unknown) {
  const r = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// ===================================================================== SHELL
export default function Cockpit() {
  const [tab, setTab] = useState<TabId>("operator");
  return (
    <div className="ck-root" data-testid="cockpit6">
      <div className="topbar">
        <div className="brand">
          Production Agent <span className="sub">· Verpackungslinie 1 · Werk Nord</span>
        </div>
      </div>
      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`tab ${"operator" in t && t.operator ? "operator" : ""} ${tab === t.id ? "active" : ""}`}
            data-testid={`tab-${t.id}`}
            onClick={() => setTab(t.id)}
          >
            <span className="dot" />
            {t.label}
          </button>
        ))}
      </div>
      <div className="content">
        {tab === "operator" && <OperatorTab />}
        {tab === "live" && <LiveTab />}
        {tab === "mcp" && <McpTab />}
        {tab === "rag" && <RagTab />}
        {tab === "security" && <SecurityTab />}
        {tab === "config" && <ConfigTab />}
      </div>
    </div>
  );
}
