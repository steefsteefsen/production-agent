#!/usr/bin/env python3
"""E2E-Replay: der komplette Graph gegen die ECHTEN MES/RAG-Werkzeuge über den jüngsten Replay-Fall.

Kein Fixture-Werkzeug – genau hier zeigten sich vier Integrationsfehler (tool_data-Hülle im _parse,
PackML der stehenden Station, Erstalarm in den Top-Codes, Vorfälle vor Dokumenten), die die
Unit-Tests mit Fixture-Werkzeugen nicht sahen.

LLM_MODE=mock (Standard) nutzt das deterministische Mock-LLM ohne API-Schlüssel; LLM_MODE=live ruft
ChatAnthropic (API-Schlüssel in .env). Exit 0 nur, wenn ähnliche Vorfälle gefunden wurden, eine
Maßnahme eine Vorfall-ID belegt, der Freigabeknoten erreicht ist und die Ursache stimmt.

  LLM_MODE=mock python scripts/e2e_replay.py
  LLM_MODE=live python scripts/e2e_replay.py   # Demo mit echtem Modell
"""

from __future__ import annotations

import sqlite3
import sys

from production_agent.config import get_settings
from production_agent.data.replay import score, select_replay_cases
from production_agent.graph.workflow import build_graph


def _is_incident(k: object) -> bool:
    return isinstance(k, dict) and k.get("event_id") not in (None, "")


def main() -> int:
    settings = get_settings()
    conn = sqlite3.connect(settings.mes_db_path)
    conn.row_factory = sqlite3.Row
    cases = select_replay_cases(conn, n=1)
    conn.close()
    if not cases:
        print(
            "Kein Replay-Fall verfügbar – erst 'python -m production_agent.data.simulator'.",
            file=sys.stderr,
        )
        return 1
    case = cases[-1]  # jüngster Fall
    mode = settings.llm_mode
    print(
        f"E2E-Replay: event_id={case.event_id}, Linie {case.line_id}, "
        f"SIM_NOW={case.now}, LLM_MODE={mode}"
    )

    graph = build_graph(tools=None, sim_now=case.now, llm=None)
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

    print(f"{len(alarms)} Alarme, Alarmflut={flood}")
    print(f"{n_docs} Dokumente, {n_incidents} ähnliche Vorfälle")
    print(f"{len(grounded)} mit Vorfall-ID belegt")
    print(
        f"reason_hit: {sc['reason_hit']} "
        f"(Hypothese {hypo.get('reason_code')} vs Gold {case.truth.get('reason_code')}, "
        f"Dauerfehler {sc['duration_abs_err_min']} min)"
    )
    print(f"Freigabeknoten erreicht: {bool(interrupt)}")

    ok = bool(interrupt) and n_incidents >= 1 and len(grounded) >= 1 and sc["reason_hit"]
    print("E2E OK" if ok else "E2E FEHLGESCHLAGEN")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
