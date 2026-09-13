"""Trajektorie des Graphen: Reihenfolge der Knoten ist eine Zusicherung, kein Zufall.

decisions.yaml „einfachster Graph: keine Verzweigung" → alle Szenarien
(Alarmflut, ruhige Linie, Held) folgen derselben linearen Trajektorie.

Verifikation über agentevals (Trajectory-Match, strict).
Falsifikation: verbotene Maßnahme erreicht nie die Freigabe;
               Freigabeknoten wird immer erreicht.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from agentevals.trajectory.match import create_trajectory_match_evaluator
from langchain_core.runnables import RunnableLambda
from langgraph.types import Command

from production_agent.graph.state import Hypothesis
from production_agent.graph.workflow import _ActionsOutput, build_graph
from production_agent.security.action_policy import ActionLevel, RecommendedAction

# ---------------------------------------------------------------------------
# Fixture-Tools und Fake-LLM (kopiert aus test_workflow für Eigenständigkeit)
# ---------------------------------------------------------------------------

_NOW = datetime.now(UTC)
_TS = (_NOW - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")


def _make_alarms(n: int) -> str:
    return json.dumps([{"alarm_code": "E-4711", "ts": _TS, "priority": 1} for _ in range(n)])


def _fixture_tools(alarm_count: int = 0):
    return {
        "get_line_status": lambda **_: json.dumps(
            [{"equipment_id": "EQ1", "packml_state": "Held", "ts": _TS}]
        ),
        "get_production_plan": lambda **_: json.dumps([]),
        "get_active_alarms": lambda **_: _make_alarms(alarm_count),
        "search_maintenance_docs": lambda **_: json.dumps([]),
        "find_similar_incidents": lambda **_: json.dumps([]),
        "estimate_impact": lambda **_: json.dumps(
            {"expected_downtime_min": 25.0, "cost_eur": 5000}
        ),
    }


_FAKE_HYPO = Hypothesis(
    cause="Folienriss",
    reason_code="STO-FOLIE",
    confidence=0.82,
    evidence=["E-4711"],
    expected_downtime_min=25.0,
)
_FAKE_ACTIONS = _ActionsOutput(
    actions=[
        RecommendedAction(
            title="Folie neu einlegen",
            description="Folienrolle wechseln.",
            level=ActionLevel.APPROVAL_REQUIRED,
            confidence=0.82,
            rationale="EVT-001",
        )
    ]
)
_FAKE_LLM = {
    "narrow_cause": RunnableLambda(lambda _: _FAKE_HYPO),
    "derive_actions": RunnableLambda(lambda _: _FAKE_ACTIONS),
}


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def run(alarm_count: int) -> list[str]:
    """Knotenfolge eines vollständigen Durchlaufs bis zum Interrupt."""
    g = build_graph(tools=_fixture_tools(alarm_count), llm=_FAKE_LLM)
    cfg = {"configurable": {"thread_id": f"traj-{alarm_count}"}}
    nodes: list[str] = []
    for update in g.stream({"line_id": "L1", "trace": []}, cfg, stream_mode="updates"):
        nodes.extend("approval_gate" if k == "__interrupt__" else k for k in update)
    return nodes


def as_messages(nodes: list[str]) -> list[dict]:
    """Knotenfolge ins OpenAI-Nachrichtenformat für agentevals (Knoten = Tool-Call)."""
    msgs: list[dict] = [{"role": "user", "content": "Linie L1 steht"}]
    for n in nodes:
        msgs.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": n, "arguments": "{}"}}],
            }
        )
        msgs.append({"role": "tool", "content": "ok"})
    return msgs


# ---------------------------------------------------------------------------
# Referenztrajektorie (alle Szenarien gleich – keine Verzweigung)
# ---------------------------------------------------------------------------

REF_ALLE = [
    "capture_status",
    "analyze_alarms",
    "retrieve_knowledge",
    "narrow_cause",
    "estimate_impact",
    "derive_actions",
    "approval_gate",
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_alarmflut_trajektorie_strikt():
    """Verifikation: Alarmflut (12 Alarme) folgt exakt der Referenztrajektorie."""
    nodes = run(12)
    ev = create_trajectory_match_evaluator(trajectory_match_mode="strict")
    assert ev(outputs=as_messages(nodes), reference_outputs=as_messages(REF_ALLE))["score"] is True


def test_ruhige_linie_trajektorie_identisch():
    """Verifikation: ruhige Linie (2 Alarme) – gleiche Trajektorie wie Alarmflut (keine Verzweigung)."""
    nodes = run(2)
    assert nodes == REF_ALLE
    assert "retrieve_knowledge" in nodes  # immer_wissen_abrufen: true


def test_held_trajektorie_identisch():
    """Verifikation: Held-Zustand (0 Alarme) – gleiche vollständige Trajektorie."""
    nodes = run(0)
    assert nodes == REF_ALLE


def test_ruhige_linie_hat_retrieve_knowledge_falsification():
    """Falsifikation: retrieve_knowledge MUSS in der Trajektorie sein – fehlt es, ist Routing defekt."""
    nodes = run(2)
    assert "retrieve_knowledge" in nodes, (
        f"retrieve_knowledge fehlt bei ruhiger Linie: {nodes} – Routing ist falsch"
    )


def test_verbotene_massnahme_erreicht_nie_freigabe():
    """Falsifikation der Sicherheitsschicht: Not-Aus-Überbrückung niemals in Interrupt-Payload."""
    bad_actions = _ActionsOutput(
        actions=[
            RecommendedAction(
                title="Not-Aus überbrücken damit die Linie läuft",
                description="Sicherheitskreis deaktivieren",
                level=ActionLevel.APPROVAL_REQUIRED,
                confidence=0.99,
                rationale="schnell",
            ),
            RecommendedAction(
                title="Sensor prüfen",
                description="Sensoroberfläche reinigen.",
                level=ActionLevel.INFORM,
                confidence=0.9,
                rationale="EVT-001",
            ),
        ]
    )
    fake_llm = {
        "narrow_cause": RunnableLambda(lambda _: _FAKE_HYPO),
        "derive_actions": RunnableLambda(lambda _: bad_actions),
    }
    g = build_graph(tools=_fixture_tools(12), llm=fake_llm)
    cfg = {"configurable": {"thread_id": "traj-forbidden"}}
    last = {}
    for update in g.stream({"line_id": "L1", "trace": []}, cfg, stream_mode="updates"):
        last = update
    payload = last["__interrupt__"][0].value
    assert all("Not-Aus" not in a["title"] for a in payload["actions"])


def test_freigabe_immer_erreichbar_und_resumebar():
    """Verifikation: approval_gate ist immer erreichbar und Command(resume) schließt den Graph."""
    g = build_graph(tools=_fixture_tools(0), llm=_FAKE_LLM)
    cfg = {"configurable": {"thread_id": "traj-resume"}}
    first = g.invoke({"line_id": "L1", "trace": []}, cfg)
    assert "__interrupt__" in first
    final = g.invoke(Command(resume={"approved": False, "comment": "nein"}), cfg)
    assert final["approval"]["approved"] is False
