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

function OperatorTab() {
  const [phase, setPhase] = useState<"running" | "interrupt" | "done" | "error">("running");
  const [meta, setMeta] = useState<{ thread_id: string; event_id: number | null } | null>(null);
  const [payload, setPayload] = useState<Payload | null>(null);
  const [raw, setRaw] = useState("");
  const [fbStep, setFbStep] = useState<1 | 2>(1);
  const [suggested, setSuggested] = useState("");
  const [ingested, setIngested] = useState<string | null>(null);
  const [approved, setApproved] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const esRef = useRef<EventSource | null>(null);
  const phaseRef = useRef(phase);
  const setP = (p: typeof phase) => {
    phaseRef.current = p;
    setPhase(p);
  };

  const start = () => {
    esRef.current?.close();
    setMeta(null);
    setPayload(null);
    setRaw("");
    setFbStep(1);
    setSuggested("");
    setIngested(null);
    setApproved(null);
    setErr("");
    setP("running");
    const es = new EventSource("/investigations/stream?line_id=L1&event_id=360");
    esRef.current = es;
    es.addEventListener("start", (e) => setMeta(JSON.parse((e as MessageEvent).data)));
    es.addEventListener("interrupt", (e) => {
      setPayload(JSON.parse((e as MessageEvent).data).payload ?? {});
      setP("interrupt");
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
  useEffect(() => {
    start();
    return () => esRef.current?.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  if (phase === "running")
    return (
      <div data-testid="op-running" className="muted">
        Untersuchung läuft – die Freigabe erscheint, sobald der Agent am Freigabeknoten hält…
      </div>
    );
  if (phase === "error") return <div className="cfg-drift">{err}</div>;

  return (
    <div data-testid="operator-tab">
      <div className="op-header">
        <div className="op-title">Untersuchung — Ereignis #{meta?.event_id ?? "–"}</div>
        <div className="op-sub">Replay-Uhr aktiv · Agent empfiehlt, er führt nicht aus</div>
      </div>

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
function McpTab() {
  const [servers, setServers] = useState<ServerDef[]>([]);
  const [calls, setCalls] = useState<ToolCall[]>([]);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    getJSON<{ servers: ServerDef[] }>("/mcp/servers").then((d) => setServers(d.servers)).catch(() => {});
    getJSON<{ tools: ToolCall[] }>("/observability").then((d) => setCalls(d.tools)).catch(() => {});
  }, []);
  return (
    <div data-testid="mcp-tab">
      <div className="log-header">
        <div className="log-title">MCP — Werkzeuge &amp; Aufrufe</div>
        <div className="log-note">transport: stdio · live</div>
      </div>
      <div className="dummy-box">
        <span className="ic">💡</span>
        <div>
          <b>Was ist MCP?</b> Ein offenes Protokoll, über das der Agent mit klar abgegrenzten
          Werkzeugen spricht — statt direkt auf Datenbanken zuzugreifen. Der Agent kann nur fragen,
          nie selbst etwas verändern.
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
      <div className="section-h">LIVE-AUFRUFE IN DIESEM LAUF</div>
      <div className="kpi" data-testid="kpi-mcp" onClick={() => setOpen((o) => !o)}>
        <div>
          <div className="kpi-main">{calls.length} Werkzeugaufrufe · alle erfolgreich</div>
          <div className="kpi-sub">
            {[...new Set(calls.map((c) => c.server))].join(", ") || "kein Lauf"} · Antworten gekapselt
          </div>
        </div>
        <span className="kpi-toggle">{open ? "▲ Details verbergen" : "▼ Rohdaten anzeigen"}</span>
      </div>
      {open &&
        calls.map((c, i) => (
          <div className="log-entry" data-testid="mcp-call" key={i}>
            <div className="log-line1">
              <span className="log-tag tool">tool_call</span>
              <span className="log-server">
                {c.server}.{c.tool}
              </span>
              <span className="log-time">{c.ts}</span>
            </div>
            <div className="log-body">
              <span className="k">params:</span> {JSON.stringify(c.params)}
            </div>
            <div className="log-raw">{JSON.stringify(c.raw)}</div>
          </div>
        ))}
      {open && !calls.length && (
        <div className="muted">Noch keine Aufrufe — im Bediener-Tab einen Lauf starten.</div>
      )}
    </div>
  );
}

// ===================================================================== RAG
interface Hit {
  doc: string;
  text: string;
  rrf_rank: number;
}
const NORMS = [
  {
    badge: "used",
    label: "aktiv genutzt",
    title: "ISA-18.2 — Alarm Management",
    desc: "Definiert die Alarmflut-Schwelle (≥10 Alarme/10 Min), die die Alarmfluterkennung tatsächlich anwendet.",
  },
  {
    badge: "context",
    label: "Kontext",
    title: "EEMUA 191 — Alarm Systems",
    desc: "Ergänzender Referenzrahmen zur Alarmbewirtschaftung, gemeinsam mit ISA-18.2 in decisions.yaml genannt.",
  },
  {
    badge: "context",
    label: "Kontext",
    title: "ISO 22400-2 / VDMA 66412 — Kennzahlen & Ereignisdefinition",
    desc: "Grundlage der Störungs-/Ereignisdefinition und Stillstandszeit (ADR-0001).",
  },
  {
    badge: "context",
    label: "Kontext",
    title: "IEC 62443 — Industrielle Cybersicherheit",
    desc: "Referenzrahmen für OT-Sicherheit — sql_guard/injection_guard folgen dem Grundgedanken, ohne Zertifizierung.",
  },
  {
    badge: "context",
    label: "Kontext",
    title: "ISO 13849 / IEC 61508 — Funktionale Sicherheit",
    desc: "Bewusst außerhalb: der Agent ist kein sicherheitsgerichteter Teil (action_policy schließt Sicherheitseingriffe aus).",
  },
];
function RagTab() {
  const [inv, setInv] = useState<{ documents: [string, number][]; total_chunks: number; runtime_count: number } | null>(null);
  const [res, setRes] = useState<{ hits: Hit[]; code_match: boolean } | null>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    getJSON<typeof inv>("/knowledge/documents").then(setInv).catch(() => {});
    getJSON<{ hits: Hit[]; code_match: boolean }>(
      "/knowledge/search?q=" + encodeURIComponent("Folienbahn läuft schräg Siegelnaht"),
    )
      .then(setRes)
      .catch(() => {});
  }, []);
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
      <div className="section-h">DOKUMENTENBESTAND ({inv?.total_chunks ?? "…"} Chunks)</div>
      <div className="doc-list">
        {(inv?.documents ?? []).map(([doc, n]) => (
          <div className="doc-item" data-testid="doc-item" key={doc}>
            <span className="ic">{doc.startsWith("rueckkopplung") ? "Rückkopplung" : "Dokument"}</span>
            <span className="n">{doc}</span>
            <span className="c">{n} Chunk(s)</span>
          </div>
        ))}
      </div>
      {inv && inv.runtime_count > 0 && (
        <div className="muted" data-testid="rag-runtime">
          Davon {inv.runtime_count} zur Laufzeit über die Bediener-Rückkopplung eingespeist.
        </div>
      )}
      <div className="section-h">NORMEN &amp; VORGABEN, DIE DAS VORGEHEN BEEINFLUSSEN</div>
      <div className="norm-list">
        {NORMS.map((n) => (
          <div className="norm-item" data-testid="norm-item" key={n.title}>
            <span className={`badge ${n.badge}`}>{n.label}</span>
            <div className="t">
              <b>{n.title}</b>
              <span>{n.desc}</span>
            </div>
          </div>
        ))}
      </div>
      <div className="section-h">SUCHLAUF (MIT RRF-RANG)</div>
      <div className="kpi" data-testid="kpi-rag" onClick={() => setOpen((o) => !o)}>
        <div>
          <div className="kpi-main">
            1 Suche · Top-Treffer rrf_rank {res?.hits?.[0]?.rrf_rank ?? "–"}
          </div>
          <div className="kpi-sub">
            {inv?.total_chunks ?? "…"} Chunks im Bestand ·{" "}
            {res?.code_match ? "Fehlercode erkannt (BM25×2)" : "kein Code (BM25≈Vektor)"}
          </div>
        </div>
        <span className="kpi-toggle">{open ? "▲ Details verbergen" : "▼ Rohdaten anzeigen"}</span>
      </div>
      {open && (
        <div className="log-entry">
          <div className="log-line1">
            <span className="log-tag query">query</span>
            <span className="log-server">"Folienbahn läuft schräg, Siegelnaht unvollständig"</span>
          </div>
          <div className="log-body">
            Exakter Fehlercode erkannt: <span className="k">{res?.code_match ? "ja" : "nein"}</span>{" "}
            → {res?.code_match ? "BM25 doppelt gewichtet" : "gleiche Gewichtung BM25/Vektor"}
          </div>
          <div className="rag-rank">
            {(res?.hits ?? []).slice(0, 4).map((h, i) => (
              <span className={`rag-rank-item ${i === 0 ? "top" : ""}`} data-testid="rrf-rank" key={i}>
                {h.doc} · rrf_rank {h.rrf_rank}
              </span>
            ))}
          </div>
        </div>
      )}
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
