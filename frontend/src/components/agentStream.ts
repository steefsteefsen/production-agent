// Reine Stream-Reduktion (ohne React, damit testbar): SSE-Events des Untersuchungs-Graphen
// → Kartenzustand je Knoten. Knotennamen/Reihenfolge exakt aus graph/workflow.py
// (linear, keine Verzweigung; approval_gate ist der interrupt/Freigabeknoten).

export type CardStatus = "wartend" | "läuft" | "fertig" | "freigabe";

export interface NodeCard {
  id: string;
  label: string;
  status: CardStatus;
  summary: string;
  payload?: Record<string, unknown>;
}

export const NODE_ORDER = [
  "capture_status",
  "analyze_alarms",
  "retrieve_knowledge",
  "narrow_cause",
  "estimate_impact",
  "derive_actions",
  "approval_gate",
] as const;

export const NODE_LABEL: Record<string, string> = {
  capture_status: "1 · Linienstatus & Plan",
  analyze_alarms: "2 · Alarme analysieren",
  retrieve_knowledge: "3 · Wissen abrufen",
  narrow_cause: "4 · Ursache eingrenzen",
  estimate_impact: "5 · Wirkung schätzen",
  derive_actions: "6 · Maßnahmen ableiten",
  approval_gate: "7 · Freigabe",
};

export function initialCards(): NodeCard[] {
  return NODE_ORDER.map((id) => ({
    id,
    label: NODE_LABEL[id],
    status: "wartend" as CardStatus,
    summary: "",
  }));
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

function num(x: unknown): number | null {
  const n = Number(x);
  return Number.isFinite(n) ? n : null;
}

/** Kompakte, menschenlesbare Zusammenfassung der Knotenausgabe (aus dem SSE-payload). */
export function summarize(node: string, payload: Record<string, unknown>): string {
  const p = payload ?? {};
  switch (node) {
    case "capture_status": {
      const plan = Array.isArray(p.production_plan) ? p.production_plan.length : 0;
      return `Linienstatus erfasst · ${plan} Auftr.${plan === 1 ? "" : "äge"} im Plan`;
    }
    case "analyze_alarms": {
      const alarms = Array.isArray(p.alarms) ? p.alarms.length : 0;
      const flood = Boolean(p.alarm_flood);
      return `${alarms} Alarme · ${flood ? "Alarmflut erkannt" : "keine Flut"}`;
    }
    case "retrieve_knowledge": {
      const k = Array.isArray(p.knowledge) ? (p.knowledge as unknown[]) : [];
      const inc = k.filter(isIncident).length;
      const docs = k.length - inc;
      return `${inc} ähnliche Vorfälle · ${docs} Dokumente`;
    }
    case "narrow_cause": {
      const h = (p.hypothesis ?? {}) as Record<string, unknown>;
      const conf = num(h.confidence);
      const c = conf !== null ? conf.toFixed(2) : "–";
      return `Hypothese: ${h.reason_code ?? "?"} · Konfidenz ${c}`;
    }
    case "estimate_impact": {
      const im = (p.impact ?? {}) as Record<string, unknown>;
      const cost = num(im.cost_eur) ?? num(im.downtime_cost_eur) ?? num(im.lost_value_eur);
      const risk = Array.isArray(im.orders_at_risk) ? im.orders_at_risk.length : null;
      const parts: string[] = [];
      if (cost !== null) parts.push(`${Math.round(cost).toLocaleString("de-DE")} € Wirkung`);
      if (risk !== null) parts.push(`${risk} gefährdete Aufträge`);
      return parts.length ? parts.join(" · ") : "Wirkung geschätzt";
    }
    case "derive_actions": {
      const n = Array.isArray(p.actions) ? p.actions.length : 0;
      return `${n} Maßnahme${n === 1 ? "" : "n"} · alle mit Vorfall-ID belegt`;
    }
    case "approval_gate":
      return "Freigabe erforderlich – Mensch entscheidet";
    default:
      return "";
  }
}

export interface StreamEvent {
  kind: "start" | "node" | "interrupt";
  node?: string;
  payload?: Record<string, unknown>;
}

/** Wendet ein Stream-Ereignis auf den Kartenzustand an (rein, keine Seiteneffekte). */
export function applyEvent(cards: NodeCard[], ev: StreamEvent): NodeCard[] {
  const next = cards.map((c) => ({ ...c }));
  const idxOf = (id: string) => next.findIndex((c) => c.id === id);

  if (ev.kind === "start") {
    if (next[0]) next[0].status = "läuft";
    return next;
  }
  if (ev.kind === "interrupt") {
    // alle Vorknoten gelten als fertig, der Freigabeknoten wartet auf den Menschen
    for (const c of next) if (c.id !== "approval_gate" && c.status !== "fertig") c.status = "fertig";
    const gi = idxOf("approval_gate");
    if (gi >= 0) {
      next[gi].status = "freigabe";
      next[gi].summary = summarize("approval_gate", ev.payload ?? {});
      next[gi].payload = ev.payload;
    }
    return next;
  }
  // node
  const i = ev.node ? idxOf(ev.node) : -1;
  if (i >= 0) {
    // frühere noch wartende Knoten sicherheitshalber abschließen
    for (let j = 0; j < i; j++) if (next[j].status === "wartend") next[j].status = "fertig";
    next[i].status = "fertig";
    next[i].summary = summarize(ev.node!, ev.payload ?? {});
    next[i].payload = ev.payload;
    if (next[i + 1] && next[i + 1].status === "wartend") next[i + 1].status = "läuft";
  }
  return next;
}
