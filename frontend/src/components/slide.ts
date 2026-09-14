// Leitet die „Eingangswerte" je Graph-Knoten aus den bereits vorhandenen Karten-Payloads ab
// (der Eingang eines Knotens = Ausgabe der Vorknoten). Rein funktional, kein Backend nötig.
// Wird in der aufgeklappten Schritt-Karte als Block „EINGANG" gezeigt (Eingang → Transformation
// → Bewertung).

import type { NodeCard } from "./agentStream.ts";

export interface InputRow {
  label: string;
  value: string;
}

export interface RunMeta {
  line_id?: string;
  sim_now?: string | null;
  event_id?: number | null;
  mode?: string;
}

function num(x: unknown): number | null {
  const n = Number(x);
  return Number.isFinite(n) ? n : null;
}

function isIncident(k: unknown): boolean {
  return (
    typeof k === "object" &&
    k !== null &&
    "event_id" in k &&
    (k as { event_id: unknown }).event_id !== null &&
    (k as { event_id: unknown }).event_id !== ""
  );
}

function payloadOf(cards: NodeCard[], id: string): Record<string, unknown> {
  return (cards.find((c) => c.id === id)?.payload ?? {}) as Record<string, unknown>;
}

function euro(x: number | null): string {
  return x !== null ? `${Math.round(x).toLocaleString("de-DE")} €` : "–";
}

/** Eingangswerte eines Knotens, abgeleitet aus den Ausgaben der Vorknoten (reale Werte). */
export function nodeInputRows(nodeId: string, cards: NodeCard[], meta: RunMeta | null): InputRow[] {
  const cap = payloadOf(cards, "capture_status");
  const ala = payloadOf(cards, "analyze_alarms");
  const kno = payloadOf(cards, "retrieve_knowledge");
  const nar = payloadOf(cards, "narrow_cause");
  const imp = payloadOf(cards, "estimate_impact");
  const der = payloadOf(cards, "derive_actions");
  const chk = payloadOf(cards, "check_evidence");

  const alarms = Array.isArray(ala.alarms) ? ala.alarms.length : 0;
  const flood = Boolean(ala.alarm_flood);
  const know = Array.isArray(kno.knowledge) ? (kno.knowledge as unknown[]) : [];
  const inc = know.filter(isIncident).length;
  const docs = know.length - inc;
  const hyp = (nar.hypothesis ?? {}) as Record<string, unknown>;
  const impact = (imp.impact ?? {}) as Record<string, unknown>;
  const actions = Array.isArray(der.actions) ? der.actions.length : 0;
  const jr = Array.isArray(chk.judge_results)
    ? (chk.judge_results as Array<{ verified?: boolean }>)
    : [];
  const cost = num(impact.cost_eur) ?? num(impact.downtime_cost_eur) ?? num(impact.lost_value_eur);
  const conf = num(hyp.confidence);
  const downtime = num(hyp.expected_downtime_min);

  switch (nodeId) {
    case "capture_status":
      return [
        { label: "Linie", value: meta?.line_id ?? "L1" },
        { label: "Ereignis", value: meta?.event_id != null ? String(meta.event_id) : "–" },
        { label: "Replay-Uhr", value: meta?.sim_now ?? "–" },
      ];
    case "analyze_alarms": {
      const plan = Array.isArray(cap.production_plan) ? cap.production_plan.length : 0;
      return [
        { label: "Linienstatus", value: "erfasst" },
        { label: "Aufträge im Plan", value: String(plan) },
      ];
    }
    case "retrieve_knowledge":
      return [
        { label: "Alarme", value: String(alarms) },
        { label: "Alarmflut", value: flood ? "ja" : "nein" },
      ];
    case "narrow_cause":
      return [
        { label: "Alarme", value: String(alarms) },
        { label: "Alarmflut", value: flood ? "ja" : "nein" },
        { label: "Ähnliche Vorfälle", value: String(inc) },
        { label: "Dokumente", value: String(docs) },
      ];
    case "estimate_impact":
      return [
        { label: "Hypothese", value: String(hyp.reason_code ?? "–") },
        { label: "erwartete Stillstandszeit", value: downtime !== null ? `${downtime} min` : "–" },
      ];
    case "derive_actions":
      return [
        { label: "Hypothese", value: String(hyp.reason_code ?? "–") },
        { label: "Konfidenz", value: conf !== null ? conf.toFixed(2) : "–" },
        { label: "Wirkung", value: euro(cost) },
        { label: "Ähnliche Vorfälle (Belegquelle)", value: String(inc) },
      ];
    case "check_evidence":
      return [
        { label: "Maßnahmen", value: String(actions) },
        { label: "zitierte Belege", value: "je Maßnahme, nur Beleg im Original (ohne Begründung)" },
      ];
    case "approval_gate": {
      const ok = jr.filter((r) => r && r.verified).length;
      return [
        { label: "Maßnahmen", value: String(actions) },
        { label: "vom Judge bestätigt", value: jr.length ? `${ok}/${jr.length}` : "–" },
        { label: "Wirkung", value: euro(cost) },
      ];
    }
    default:
      return [];
  }
}
