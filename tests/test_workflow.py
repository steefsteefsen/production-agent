"""Der Graph hält am Freigabeknoten an und läuft nach Command(resume=...) zu Ende."""

from langgraph.types import Command

from production_agent.graph.workflow import build_graph


def test_graph_interrupts_at_approval_and_resumes():  # Verifikation + Falsifikation (FORBIDDEN entfernt)
    graph = build_graph()  # InMemorySaver
    cfg = {"configurable": {"thread_id": "t1"}}
    actions = [
        {"title": "Motor M2 neu starten", "description": "", "confidence": 0.85},
        {"title": "Not-Aus überbrücken", "description": "", "confidence": 0.99},
    ]
    first = graph.invoke(
        {"line_id": "L1", "alarms": [{}] * 12, "actions": actions, "trace": []}, cfg
    )
    assert "__interrupt__" in first
    payload = first["__interrupt__"][0].value
    assert [a["title"] for a in payload["actions"]] == [
        "Motor M2 neu starten"
    ]  # FORBIDDEN entfernt
    assert any(t.startswith("3 Wissen") for t in first["trace"])  # Alarmflut → RAG-Zweig

    final = graph.invoke(Command(resume={"approved": True, "comment": "ok"}), cfg)
    assert final["approval"]["approved"] is True
    assert final["trace"][-1].startswith("7 Freigabe")
