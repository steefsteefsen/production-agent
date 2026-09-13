#!/usr/bin/env python3
"""E2E-Replay: der komplette Graph gegen die ECHTEN MES/RAG-Werkzeuge über einen Replay-Fall.

Kein Fixture-Werkzeug – genau hier zeigten sich vier Integrationsfehler (tool_data-Hülle im _parse,
PackML der stehenden Station, Erstalarm in den Top-Codes, Vorfälle vor Dokumenten), die die
Unit-Tests mit Fixture-Werkzeugen nicht sahen.

Fälle und Entscheidungspfade (Testmatrix docs/testplan_e2e.md):
  --event-id <ID>   Replay-Fall wählen (Default: jüngstes Gold-Ereignis, derzeit 360, STO-FOLIE).
                    Beispiel E2: 336 (STO-ANTRIEB, Prio 1, andere Kategorie, >5 min).
  --decision none    (Default) bis zum Freigabeknoten laufen und anhalten (Empfehlen ≠ Ausführen).
  --decision approve nach dem interrupt() über den SQLite-Checkpointer fortsetzen: Freigabe
                     erteilen, regulärer Abschluss, Audit-Eintrag mit Rolle.
  --decision reject  Freigabe verweigern: sauberer Abbruch ohne Abschluss, Audit-Eintrag.

LLM_MODE=mock (Standard) nutzt das deterministische Mock-LLM ohne API-Schlüssel; LLM_MODE=live ruft
ChatAnthropic (API-Schlüssel in .env). Exit 0 nur bei erwartetem Verhalten:
  none    – ähnliche Vorfälle, belegte Maßnahme, Freigabeknoten erreicht, Ursache stimmt.
  approve – zusätzlich: Fortsetzung bis Abschluss, Freigabe=erteilt, Audit-Eintrag mit Rolle.
  reject  – zusätzlich: Fortsetzung, Freigabe=verweigert, kein Maßnahmen-Abschluss, Audit-Eintrag.

  LLM_MODE=mock python scripts/e2e_replay.py
  LLM_MODE=mock python scripts/e2e_replay.py --event-id 336
  LLM_MODE=mock python scripts/e2e_replay.py --decision approve
  LLM_MODE=live python scripts/e2e_replay.py   # Demo mit echtem Modell
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any

from langgraph.types import Command

from production_agent.config import get_settings
from production_agent.data.replay import case_for_event_id, score, select_replay_cases
from production_agent.graph.workflow import build_graph

# Rolle der Freigabe im Audit (rollenbasierter Eintrag, vgl. Matrix G3/A2/A3).
_APPROVER_ROLE = "schichtleitung"


def _is_incident(k: object) -> bool:
    return isinstance(k, dict) and k.get("event_id") not in (None, "")


def _select_case(event_id: int | None):
    """Replay-Fall wählen: konkretes Ereignis (--event-id) oder das jüngste Gold-Ereignis."""
    settings = get_settings()
    conn = sqlite3.connect(settings.mes_db_path)
    conn.row_factory = sqlite3.Row
    try:
        if event_id is not None:
            return case_for_event_id(conn, event_id)
        cases = select_replay_cases(conn, n=1)
        return cases[-1] if cases else None
    finally:
        conn.close()


def _last_audit_approval() -> dict[str, Any] | None:
    """Letzten Freigabe-Eintrag (event=="approval") aus dem Audit-Log lesen (Rollenprüfung)."""
    path = Path(get_settings().audit_log_path)
    if not path.exists():
        return None
    last: dict[str, Any] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("event") == "approval":
            last = entry
    return last


def run(event_id: int | None = None, decision: str = "none") -> dict[str, Any]:
    """Einen E2E-Replay ausführen und ein deterministisches Ergebnis-Dict liefern (für D1-Hash)."""
    case = _select_case(event_id)
    if case is None:
        return {"ok": False, "error": "kein Replay-Fall", "event_id": event_id}

    # approve/reject setzen nach dem interrupt() über den SQLite-Checkpointer fort (persistent).
    checkpoint_path: str | None = None
    if decision != "none":
        checkpoint_path = str(Path(tempfile.gettempdir()) / f"e2e_ckpt_{case.event_id}.sqlite")
        Path(checkpoint_path).unlink(missing_ok=True)  # frischer Thread je Lauf

    graph = build_graph(tools=None, sim_now=case.now, llm=None, checkpoint_path=checkpoint_path)
    cfg = {"configurable": {"thread_id": f"e2e-{case.event_id}"}}
    result = graph.invoke({"line_id": case.line_id, "trace": []}, cfg)

    alarms = result.get("alarms", []) or []
    flood = bool(result.get("alarm_flood", False))
    knowledge = result.get("knowledge", []) or []
    n_docs = sum(1 for k in knowledge if not _is_incident(k))
    n_incidents = sum(1 for k in knowledge if _is_incident(k))
    hypo = result.get("hypothesis", {}) or {}

    interrupt = result.get("__interrupt__")
    payload = interrupt[0].value if interrupt else {}
    actions = payload.get("actions", []) or []
    valid_ids = {str(k["event_id"]) for k in knowledge if _is_incident(k)}
    grounded = [a for a in actions if any(v in (a.get("rationale") or "") for v in valid_ids)]

    sc = score(hypo, case.truth)
    summary: dict[str, Any] = {
        "event_id": case.event_id,
        "line_id": case.line_id,
        "decision": decision,
        "n_alarms": len(alarms),
        "alarm_flood": flood,
        "n_docs": n_docs,
        "n_incidents": n_incidents,
        "n_grounded": len(grounded),
        "reason_code": hypo.get("reason_code"),
        "confidence": hypo.get("confidence"),
        "expected_downtime_min": hypo.get("expected_downtime_min"),
        "reason_hit": sc["reason_hit"],
        "duration_abs_err_min": sc["duration_abs_err_min"],
        "gold_reason_code": case.truth.get("reason_code"),
        "action_titles": [a.get("title") for a in actions],
        "interrupt_reached": bool(interrupt),
    }

    # Basisbedingung (Fall none): Vorfälle, belegte Maßnahme, Freigabeknoten, Ursache stimmt.
    base_ok = bool(interrupt) and n_incidents >= 1 and len(grounded) >= 1 and sc["reason_hit"]

    if decision == "none":
        summary["ok"] = base_ok
        return summary

    # approve/reject: nur sinnvoll, wenn der Freigabeknoten überhaupt erreicht wurde.
    if not interrupt:
        summary["ok"] = False
        summary["error"] = "kein Freigabeknoten erreicht – Fortsetzung nicht möglich"
        return summary

    approved = decision == "approve"
    resume_value = {
        "thread_id": cfg["configurable"]["thread_id"],
        "approved": approved,
        "role": _APPROVER_ROLE,
        "by": "e2e-replay",
        "comment": "E2E-Replay Freigabe" if approved else "E2E-Replay Ablehnung",
    }
    final = graph.invoke(Command(resume=resume_value), cfg)

    approval = final.get("approval") or {}
    resumed_to_end = not final.get("__interrupt__")
    audit = _last_audit_approval() or {}
    audit_decision = audit.get("decision") or {}
    audit_ok = (
        audit.get("event") == "approval"
        and bool(audit_decision.get("role"))
        and audit_decision.get("approved") is approved
    )

    summary["approved"] = approval.get("approved")
    summary["approval_role"] = approval.get("role") if isinstance(approval, dict) else None
    summary["resumed_to_end"] = resumed_to_end
    summary["audit_role"] = audit_decision.get("role")

    if approved:
        # Freigabe erteilt: regulärer Abschluss, Freigabe=erteilt, Audit-Eintrag mit Rolle.
        summary["ok"] = base_ok and resumed_to_end and approval.get("approved") is True and audit_ok
    else:
        # Freigabe verweigert: sauberer Abbruch, kein Maßnahmen-Abschluss, Audit-Eintrag mit Rolle.
        summary["ok"] = (
            base_ok and resumed_to_end and approval.get("approved") is False and audit_ok
        )
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="E2E-Replay des Production-Agent-Graphen")
    ap.add_argument(
        "--event-id",
        type=int,
        default=None,
        help="Gold-Ereignis für den Replay-Fall (Default: jüngstes, derzeit 360)",
    )
    ap.add_argument(
        "--decision",
        choices=["none", "approve", "reject"],
        default="none",
        help="Verhalten am Freigabeknoten (Default: none = anhalten)",
    )
    args = ap.parse_args(argv)

    s = run(event_id=args.event_id, decision=args.decision)
    if s.get("error") and s.get("event_id") is not None and "reason_code" not in s:
        print(s["error"], file=sys.stderr)
        return 1

    print(
        f"E2E-Replay: event_id={s['event_id']}, Linie {s['line_id']}, "
        f"LLM_MODE={get_settings().llm_mode}, decision={s['decision']}"
    )
    print(f"{s['n_alarms']} Alarme, Alarmflut={s['alarm_flood']}")
    print(f"{s['n_docs']} Dokumente, {s['n_incidents']} ähnliche Vorfälle")
    print(f"{s['n_grounded']} mit Vorfall-ID belegt")
    print(
        f"reason_hit: {s['reason_hit']} "
        f"(Hypothese {s['reason_code']} vs Gold {s['gold_reason_code']}, "
        f"Dauerfehler {s['duration_abs_err_min']} min)"
    )
    print(f"Freigabeknoten erreicht: {s['interrupt_reached']}")
    if s["decision"] != "none":
        print(
            f"Fortsetzung: Freigabe={'erteilt' if s.get('approved') else 'verweigert'}, "
            f"Abschluss={s.get('resumed_to_end')}, Audit-Rolle={s.get('audit_role')}"
        )
    print("E2E OK" if s.get("ok") else "E2E FEHLGESCHLAGEN")
    return 0 if s.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
