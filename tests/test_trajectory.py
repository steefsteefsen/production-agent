"""Trajektorie des Graphen: Reihenfolge der Knoten und Werkzeuge ist eine Zusicherung, kein Zufall.
Verifikation über agentevals (Trajectory-Match); Falsifikation: verbotene Maßnahme erreicht nie die Freigabe,
ohne Alarmflut kein RAG-Zweig, Freigabeknoten wird immer erreicht."""

from __future__ import annotations

from agentevals.trajectory.match import create_trajectory_match_evaluator
from langgraph.types import Command

from production_agent.graph.workflow import build_graph


def run(alarms: int, actions: list[dict]) -> tuple[list[str], dict]:
    g = build_graph()
    cfg = {"configurable": {"thread_id": f"t-{alarms}"}}
    nodes: list[str] = []
    last: dict = {}
    for update in g.stream(
        {"line_id": "L1", "alarms": [{}] * alarms, "actions": actions, "trace": []},
        cfg,
        stream_mode="updates",
    ):
        nodes.extend("approval_gate" if k == "__interrupt__" else k for k in update)
        last = update
    return nodes, last


def as_messages(nodes: list[str]) -> list[dict]:
    """Knotenfolge in das OpenAI-Nachrichtenformat, das agentevals vergleicht (Knoten = Tool-Call)."""
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


REF_FLOOD = [
    "capture_status",
    "analyze_alarms",
    "retrieve_knowledge",
    "narrow_cause",
    "estimate_impact",
    "derive_actions",
    "approval_gate",
]
REF_QUIET = [
    "capture_status",
    "analyze_alarms",
    "narrow_cause",
    "estimate_impact",
    "derive_actions",
    "approval_gate",
]


def test_flood_trajectory_matches_reference_strictly():
    nodes, _ = run(12, [{"title": "Motor prüfen", "description": "", "confidence": 0.9}])
    ev = create_trajectory_match_evaluator(trajectory_match_mode="strict")
    assert ev(outputs=as_messages(nodes), reference_outputs=as_messages(REF_FLOOD))["score"] is True


def test_quiet_line_skips_rag_branch():  # Falsifikation der Verzweigung
    nodes, _ = run(2, [{"title": "Sensor reinigen", "description": "", "confidence": 0.9}])
    assert nodes == REF_QUIET
    assert "retrieve_knowledge" not in nodes


def test_forbidden_action_never_reaches_approval():  # Falsifikation der Sicherheitsschicht
    bad = {
        "title": "Not-Aus überbrücken",
        "description": "damit es weiterläuft",
        "confidence": 0.99,
    }
    _, last = run(12, [bad, {"title": "Prüfe Sensor", "description": "", "confidence": 0.9}])
    payload = last["__interrupt__"][0].value
    assert all("Not-Aus" not in a["title"] for a in payload["actions"])


def test_approval_always_reached_and_resumable():
    g = build_graph()
    cfg = {"configurable": {"thread_id": "t-resume"}}
    first = g.invoke({"line_id": "L1", "alarms": [], "actions": [], "trace": []}, cfg)
    assert (
        "__interrupt__" in first
    )  # auch ohne Alarme und Maßnahmen wartet der Graph auf den Menschen
    final = g.invoke(Command(resume={"approved": False, "comment": "nein"}), cfg)
    assert final["approval"]["approved"] is False
