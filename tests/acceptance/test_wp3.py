"""Abnahmetest WP3 – Spezifikation aus docs/test_cases.md. Unveränderbar (Guardian K7).

Übersprungen, solange WP3 nicht gebaut ist (kein xfail). Sobald das Kern-Artefakt existiert, laufen
die Fälle und der Builder muss sie grün machen (gate_no_skip.py verlangt 0 Skips)."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "src/production_agent/graph/prompts.py"
pytestmark = pytest.mark.skipif(not ARTIFACT.exists(), reason="WP3 noch nicht gebaut")


def test_wp3_kernartefakt_vorhanden():
    # Verifikation: das in plan.yaml/tasks.yaml zugesagte Kern-Artefakt existiert
    assert ARTIFACT.exists()


def test_wp3_artefakt_nicht_leer_falsification():
    # Falsifikation: ein leeres Artefakt zählt nicht als erfüllt
    assert ARTIFACT.stat().st_size > 0


# --- Stefan-Zusatzentscheidung (a): jede Maßnahme nennt eine Vorfall-ID aus downtime_events_gold ---

import json  # noqa: E402
from datetime import UTC, datetime, timedelta  # noqa: E402

_ALARM_TS = (datetime.now(UTC) - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")


def _acc_tools():
    return {
        "get_line_status": lambda **_: json.dumps(
            [{"equipment_id": "EQ1", "packml_state": "Held", "ts": _ALARM_TS}]
        ),
        "get_production_plan": lambda **_: json.dumps(
            [{"order_id": "ORD1", "planned_qty": 1000, "produced_qty": 500}]
        ),
        "get_active_alarms": lambda **_: json.dumps(
            [{"alarm_code": "E-4711", "ts": _ALARM_TS, "priority": 1} for _ in range(12)]
        ),
        "search_maintenance_docs": lambda **_: json.dumps(
            [{"chunk_id": "doc1#0", "text": "Folienriss: Folie pruefen", "score_bm25": 1.2}]
        ),
        "find_similar_incidents": lambda **_: json.dumps(
            [{"event_id": "EVT-001", "reason_code": "STO-FOLIE", "duration_min": 25}]
        ),
        "estimate_impact": lambda **_: json.dumps(
            {"expected_downtime_min": 25.0, "lost_units": 1500, "cost_eur": 5000.0, "orders_at_risk": ["ORD1"]}
        ),
    }


def _acc_run(actions, thread):
    from langchain_core.runnables import RunnableLambda

    from production_agent.graph.state import Hypothesis
    from production_agent.graph.workflow import build_graph

    hyp = Hypothesis(
        cause="Folienriss",
        reason_code="STO-FOLIE",
        confidence=0.82,
        evidence=["E-4711", "EVT-001"],
        expected_downtime_min=25.0,
    )
    llm = {
        "narrow_cause": RunnableLambda(lambda _: hyp),
        "derive_actions": RunnableLambda(lambda _: actions),
    }
    g = build_graph(tools=_acc_tools(), llm=llm)
    return g.invoke({"line_id": "L1", "trace": []}, {"configurable": {"thread_id": thread}})


def _acc_actions(*rationales):
    from production_agent.graph.workflow import _ActionsOutput
    from production_agent.security.action_policy import ActionLevel, RecommendedAction

    return _ActionsOutput(
        actions=[
            RecommendedAction(
                title=f"Massnahme {i}",
                description="Konkreter Schritt.",
                level=ActionLevel.APPROVAL_REQUIRED,
                confidence=0.82,
                rationale=r,
            )
            for i, r in enumerate(rationales)
        ]
    )


def test_wp3_jede_massnahme_nennt_vorfall_id():
    """(a) Verifikation: jede in der Freigabe verbleibende Massnahme nennt eine Vorfall-ID (EVT-001)
    aus den ähnlichen Vorfaellen (downtime_events_gold)."""
    result = _acc_run(_acc_actions("E-4711 historisch -> STO-FOLIE (EVT-001)"), "wp3-acc-vorfallid-1")
    payload = result["__interrupt__"][0].value
    assert len(payload["actions"]) >= 1
    assert all("EVT-001" in a["rationale"] for a in payload["actions"])


def test_wp3_massnahme_ohne_vorfall_id_verworfen_falsification():
    """(a) Falsifikation: eine Massnahme ohne belegende Vorfall-ID erreicht die Freigabe nicht."""
    result = _acc_run(
        _acc_actions("Beleg: EVT-001", "reine Behauptung ohne Vorfall-ID"),
        "wp3-acc-vorfallid-2",
    )
    payload = result["__interrupt__"][0].value
    rationales = [a["rationale"] for a in payload["actions"]]
    assert any("EVT-001" in r for r in rationales)
    assert all("EVT-001" in r for r in rationales)  # die unbelegte Massnahme wurde verworfen
