// Laufbegleitender Erzähltext je Graph-Knoten. Alle Bausteine werden aus den ECHTEN SSE-Feldern
// befüllt (nie hartkodiert), reine Funktionen ohne React – testbar und deckungsgleich mit den
// Feldern aus agentStream.summarize(). Der Abschlusstext gleicht die Hypothese gegen die
// verborgene Gold-Wahrheit ab (reason_hit) – erst NACH der Freigabe (ADR-0002).

import type { NodeCard } from "./agentStream.ts";

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

export const INTRO =
  "Der Agent untersucht die stehende Linie Schritt für Schritt – er empfiehlt, er führt nicht aus.";

/** Erzähltext für eine Knoten-Karte, befüllt aus ihrem SSE-payload. Leerer String ohne Daten. */
export function nodeNarrative(card: NodeCard): string {
  const p = (card.payload ?? {}) as Record<string, unknown>;
  switch (card.id) {
    case "capture_status": {
      const plan = Array.isArray(p.production_plan) ? p.production_plan.length : 0;
      return `Linienstatus und Produktionsplan erfasst: ${plan} Auftr${plan === 1 ? "ag" : "äge"} im Plan.`;
    }
    case "analyze_alarms": {
      const alarms = Array.isArray(p.alarms) ? p.alarms.length : 0;
      const flood = Boolean(p.alarm_flood);
      return flood
        ? `${alarms} Alarme ausgewertet – Alarmflut erkannt, der Lauf verzweigt in den Wissensabruf.`
        : `${alarms} Alarme ausgewertet – keine Alarmflut.`;
    }
    case "retrieve_knowledge": {
      const k = Array.isArray(p.knowledge) ? (p.knowledge as unknown[]) : [];
      const inc = k.filter(isIncident).length;
      const docs = k.length - inc;
      return `Historisches Wissen abgerufen: ${inc} ähnliche Vorfälle und ${docs} Wartungsdokumente.`;
    }
    case "narrow_cause": {
      const h = (p.hypothesis ?? {}) as Record<string, unknown>;
      const conf = num(h.confidence);
      const c = conf !== null ? conf.toFixed(2) : "–";
      return `Ursache eingegrenzt: Hypothese ${h.reason_code ?? "?"} bei Konfidenz ${c}.`;
    }
    case "estimate_impact": {
      const im = (p.impact ?? {}) as Record<string, unknown>;
      const cost = num(im.cost_eur) ?? num(im.downtime_cost_eur) ?? num(im.lost_value_eur);
      const risk = Array.isArray(im.orders_at_risk) ? im.orders_at_risk.length : null;
      const parts: string[] = [];
      if (cost !== null) parts.push(`${Math.round(cost).toLocaleString("de-DE")} € geschätzte Wirkung`);
      if (risk !== null) parts.push(`${risk} gefährdete Aufträge`);
      return parts.length ? `Wirkung geschätzt: ${parts.join(", ")}.` : "Wirkung geschätzt.";
    }
    case "derive_actions": {
      const n = Array.isArray(p.actions) ? p.actions.length : 0;
      return `${n} Maßnahme${n === 1 ? "" : "n"} abgeleitet, jede mit Vorfall-ID belegt.`;
    }
    case "approval_gate":
      return "Freigabe erforderlich – der Agent legt Empfehlung und Belege vor, der Mensch entscheidet.";
    default:
      return "";
  }
}

export interface FinalCtx {
  approved: boolean;
  reasonHit: boolean | null;
  reasonCodePred?: string | null;
  reasonCodeGold?: string | null;
  supportedActions?: number | null;
}

/** Abschlusstext nach der Entscheidung; bei Freigabe mit reason_hit-Abgleich gegen die Gold-Wahrheit. */
export function finalNarrative(ctx: FinalCtx): string {
  if (!ctx.approved) {
    return "Untersuchung abgebrochen. Keine Maßnahme freigegeben, die Empfehlung bleibt unausgeführt. Vollständiges Audit-Log verfügbar.";
  }
  if (ctx.reasonHit === null || ctx.reasonHit === undefined) {
    return "Untersuchung abgeschlossen. Maßnahmen freigegeben. Vollständiges Audit-Log verfügbar.";
  }
  const verdict = ctx.reasonHit ? "bestätigt" : "abweichend";
  const pred = ctx.reasonCodePred ?? "?";
  return `Untersuchung abgeschlossen. Ursache ${verdict} gegen die verborgene Wahrheit (${pred} vs. Gold). Vollständiges Audit-Log verfügbar.`;
}
