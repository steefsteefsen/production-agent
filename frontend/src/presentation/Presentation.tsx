// Geführter 15-Minuten-Interview-Walkthrough als EINE React-Ansicht.
// Erreichbar direkt über :5173/presentation und per iframe im Ops-Cockpit (:8010, Tab Präsentation).
// Wiederverwendung: die bestehende Agent-Tab-Logik (<Agent/>) trägt Walkthrough + Freigabe + Ergebnis;
// hier nur Rahmen (Navigation, Fortschritt, Timer, Tokens) und die kuratierten Abschnitte drumherum.
// Alle Fachdaten kommen aus der bestehenden API (eine Quelle: data/gold/mes.sqlite), nichts hartkodiert.

import { useEffect, useRef, useState, type ReactNode } from "react";
import Agent from "../components/Agent.tsx";
import { SCOPE, STACK, type TableSpec } from "./data.ts";
import "../styles/tokens.css";

const TALK_SECONDS = 15 * 60;
const STOPPED = new Set(["Held", "Stopped", "Suspended", "Aborted", "Idle"]);

// ─────────────────────────────────────────────────────────────────────────────
// Abschnitt 1 – Intro: echter Live-Linienstatus aus /mes/line/L1
// ─────────────────────────────────────────────────────────────────────────────
interface LineData {
  line?: { name?: string; plant?: string; cost_per_downtime_minute_eur?: number };
  equipment?: { name?: string; position?: number; packml_state?: string; ts?: string }[];
}

function IntroSection() {
  const [data, setData] = useState<LineData | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    fetch("/mes/line/L1")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setData)
      .catch((e) => setErr(String(e)));
  }, []);

  const equip = data?.equipment ?? [];
  const stopped = equip.filter((e) => e.packml_state && STOPPED.has(e.packml_state));
  const steht = stopped.length > 0;
  const cost = data?.line?.cost_per_downtime_minute_eur;

  return (
    <div className="pv-fade">
      <p className="pv-kicker">1 · Ausgangslage (live)</p>
      <h1 className="pv-h1">{data?.line?.name ?? "Verpackungslinie L1"}</h1>
      {err && <p className="pv-muted">Live-Status nicht erreichbar ({err}).</p>}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--pv-gap)", marginTop: 12 }}>
        <div className="pv-card" style={steht ? { borderColor: "var(--pv-red)" } : undefined}>
          <span className={`pv-badge ${steht ? "red" : "green"}`}>
            <span className={`pv-dot ${steht ? "red" : "green"}`} /> {steht ? "Linie steht" : "Linie läuft"}
          </span>
          <p className="pv-lead" style={{ marginTop: 10 }}>
            {steht
              ? `${stopped.length} Station${stopped.length === 1 ? "" : "en"} im Stillstand${stopped[0]?.name ? ` – zuletzt: ${stopped[0].name} (${stopped[0].packml_state})` : ""}.`
              : "Alle Stationen im Normalbetrieb."}
          </p>
          {cost != null && (
            <p className="pv-mono" style={{ marginTop: 8, fontSize: 15 }}>
              Stillstandskosten: <b style={{ color: "var(--pv-red)" }}>{Math.round(cost).toLocaleString("de-DE")} €/min</b>
            </p>
          )}
        </div>
        <div className="pv-card">
          <p className="pv-kicker">Stationen (PackML)</p>
          <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
            {equip.slice(0, 6).map((e, i) => {
              const s = e.packml_state && STOPPED.has(e.packml_state);
              return (
                <div key={i} className="pv-mono" style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                  <span className={`pv-dot ${s ? "red" : "green"}`} />
                  <span style={{ flex: 1 }}>{e.name ?? `Station ${e.position}`}</span>
                  <span className="pv-muted">{e.packml_state ?? "—"}</span>
                </div>
              );
            })}
            {equip.length === 0 && !err && <span className="pv-muted">Lädt…</span>}
          </div>
        </div>
      </div>
      <p className="pv-lead" style={{ marginTop: 14 }}>
        Jede Minute kostet Geld. Die teure Zeit ist die <b>Diagnose</b> – genau hier setzt der Agent an.
      </p>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Abschnitt 2 – Datenbasis (Medallion, ein Satz)
// ─────────────────────────────────────────────────────────────────────────────
function DataSection() {
  const layers = [
    ["Bronze", "Rohdaten: Alarme, Zustände, Aufträge – wie sie anfallen."],
    ["Silber", "bereinigt & verknüpft – die Gegenwart bis „jetzt“."],
    ["Gold", "eine Zeile je Störungsereignis – die verborgene Wahrheit für die Eval."],
  ];
  return (
    <div className="pv-fade">
      <p className="pv-kicker">2 · Datenbasis</p>
      <h1 className="pv-h1">Eine Quelle, drei Schichten</h1>
      <p className="pv-lead">
        Alles läuft über <span className="pv-mono">data/gold/mes.sqlite</span> (read-only, über einen Guard) –
        Bronze → Silber → Gold, kein zweiter Datentopf.
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--pv-gap)", marginTop: 14 }}>
        {layers.map(([t, d]) => (
          <div key={t} className="pv-card">
            <p className="pv-kicker">{t}</p>
            <p style={{ marginTop: 6, fontSize: 15 }}>{d}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Abschnitt 3 – Agent-Untersuchung (WIEDERVERWENDUNG von <Agent/>): Walkthrough + Freigabe + Ergebnis
// ─────────────────────────────────────────────────────────────────────────────
function AgentSection() {
  return (
    <div className="pv-fade">
      <p className="pv-kicker">3 · Der Agent bei der Arbeit — Untersuchung, Freigabe, Ergebnis</p>
      <div className="pv-card" style={{ padding: 16 }}>
        <Agent />
      </div>
      <div className="pv-card-2" style={{ marginTop: 12 }}>
        <span className="pv-badge amber">Ehrlichkeitsgrenze (aus evals/report.md)</span>
        <p style={{ marginTop: 8, fontSize: 14 }}>
          Im Replay trifft der Agent die Ursache zuverlässig (reason_hit gegen die Gold-Wahrheit). Das ist
          eine <b>Obergrenze</b>: der Simulator kennt seine eigenen Ursachen. Kein Drift-Monitoring, kein
          Retraining – der echte Nutzen wird im Pilot mit realen Gold-Fällen gemessen.
        </p>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Abschnitt 4/5 – kuratierte Tabellen (Scope, Stack) aus data.ts
// ─────────────────────────────────────────────────────────────────────────────
function TableSection({ n, kicker, spec }: { n: number; kicker: string; spec: TableSpec }) {
  return (
    <div className="pv-fade">
      <p className="pv-kicker">{n} · {kicker}</p>
      <h2 className="pv-h2">{spec.title}</h2>
      <table className="pv-table">
        <thead><tr>{spec.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>
          {spec.rows.map((r, i) => (
            <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>
          ))}
        </tbody>
      </table>
      <p style={{ marginTop: 10, fontStyle: "italic", color: "var(--pv-accent-2)" }}>{spec.anchor}</p>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Abschnitt 6 – Abschluss / Ausblick
// ─────────────────────────────────────────────────────────────────────────────
function OutroSection() {
  return (
    <div className="pv-fade">
      <p className="pv-kicker">6 · Abschluss</p>
      <h1 className="pv-h1">Empfehlen, nicht ausführen – der schnellste Weg zu belegtem Nutzen.</h1>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "var(--pv-gap)", marginTop: 14 }}>
        <div className="pv-card"><p className="pv-kicker">Kontrolle</p><p style={{ marginTop: 6 }}>Mensch entscheidet am Freigabe-Gate, lückenloses Audit.</p></div>
        <div className="pv-card"><p className="pv-kicker">Ehrlich</p><p style={{ marginTop: 6 }}>Zweites Modell prüft Belege, Grenzen offen benannt.</p></div>
        <div className="pv-card"><p className="pv-kicker">Nächster Schritt</p><p style={{ marginTop: 6 }}>Pilot an einer Linie: MTTR vorher/nachher messen.</p></div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Shell
// ─────────────────────────────────────────────────────────────────────────────
const SECTIONS: { label: string; body: ReactNode }[] = [
  { label: "Ausgangslage", body: <IntroSection /> },
  { label: "Datenbasis", body: <DataSection /> },
  { label: "Agent-Untersuchung", body: <AgentSection /> },
  { label: "Scope", body: <TableSection n={4} kicker="Scope-Entscheidungen" spec={SCOPE} /> },
  { label: "Stack", body: <TableSection n={5} kicker="Technologie-Entscheidungen" spec={STACK} /> },
  { label: "Abschluss", body: <OutroSection /> },
];

function fmt(sec: number): string {
  const m = Math.floor(Math.abs(sec) / 60);
  const s = Math.abs(sec) % 60;
  return `${sec < 0 ? "-" : ""}${m}:${String(s).padStart(2, "0")}`;
}

export default function Presentation() {
  const [i, setI] = useState(0);
  const [left, setLeft] = useState(TALK_SECONDS);
  const timer = useRef<number | null>(null);

  useEffect(() => {
    timer.current = window.setInterval(() => setLeft((v) => v - 1), 1000);
    return () => { if (timer.current) window.clearInterval(timer.current); };
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") setI((v) => Math.min(SECTIONS.length - 1, v + 1));
      if (e.key === "ArrowLeft") setI((v) => Math.max(0, v - 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const timerClass = left <= 60 ? "red" : left <= 180 ? "amber" : "green";

  return (
    <div className="pv-root" data-testid="presentation">
      <header style={{ display: "flex", alignItems: "center", gap: 16, padding: "14px 24px", borderBottom: "1px solid var(--pv-line)" }}>
        <span style={{ color: "var(--pv-accent)", fontWeight: 700 }}>Production Agent</span>
        <span className="pv-muted" style={{ fontSize: 13 }}>Geführter Walkthrough</span>
        <span className={`pv-badge ${timerClass}`} style={{ marginLeft: "auto" }} data-testid="pv-timer">
          ⏱ {fmt(left)}
        </span>
      </header>

      <div style={{ padding: "8px 24px 0" }}>
        <div className="pv-progress"><span style={{ width: `${((i + 1) / SECTIONS.length) * 100}%` }} /></div>
        <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
          {SECTIONS.map((s, k) => (
            <button
              key={s.label}
              onClick={() => setI(k)}
              className={`pv-badge ${k === i ? "green" : ""}`}
              style={{ background: k === i ? undefined : "var(--pv-surface-2)", color: k === i ? undefined : "var(--pv-muted)", border: 0, cursor: "pointer" }}
            >
              {k + 1}. {s.label}
            </button>
          ))}
        </div>
      </div>

      <main style={{ flex: 1, padding: "20px 24px", maxWidth: 1100, width: "100%", margin: "0 auto" }}>
        {SECTIONS[i].body}
      </main>

      <footer style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 24px", borderTop: "1px solid var(--pv-line)" }}>
        <button className="pv-btn ghost" onClick={() => setI((v) => Math.max(0, v - 1))} disabled={i === 0}>← Zurück</button>
        <span className="pv-muted" style={{ fontSize: 13 }}>{i + 1} / {SECTIONS.length}</span>
        <button className="pv-btn" style={{ marginLeft: "auto" }} onClick={() => setI((v) => Math.min(SECTIONS.length - 1, v + 1))} disabled={i === SECTIONS.length - 1}>Weiter →</button>
      </footer>
    </div>
  );
}
