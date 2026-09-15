"""Original-Belegtext bis in die Maßnahme durchreichen (Freigabe-Seite) und Schwelle im Payload.

Verifikation: attach_belegtext hängt je Maßnahme einen echten Dokumentsatz an (nicht nur die
Vorfall-ID), verschiedene Karten bekommen verschiedene Quellen, eine Code-Überschrift wird zum
echten Abschnittstext aufgelöst, und der Interrupt-Payload trägt die aktive Konfidenzschwelle.
Falsifikation: ohne Dokument-Chunks bleibt die Maßnahme unverändert (kein erfundener Beleg).
"""

from __future__ import annotations

import json

from langchain_core.runnables import RunnableLambda

from production_agent.graph.state import Hypothesis
from production_agent.graph.workflow import (
    _ActionsOutput,
    _HypothesesOutput,
    _original_passage,
    attach_belegtext,
    build_graph,
)
from production_agent.security.action_policy import ActionLevel, RecommendedAction


def test_attach_belegtext_haengt_echten_dokumentsatz_an():
    knowledge = [
        {"event_id": 42, "reason_code": "STO-FOLIE"},  # Vorfall (kein Dokument)
        {
            "doc": "MA-02-folienwickler.md",
            "text": "[Folienwickler] Folienriss beheben: Rolle prüfen.",
        },
        {
            "doc": "MA-03-schneidstation.md",
            "text": "[Schneidstation] Klinge kontrollieren und tauschen.",
        },
    ]
    actions = [
        {"title": "Folienriss beheben", "description": "Rolle prüfen", "confidence": 0.8},
        {"title": "Klinge prüfen", "description": "Schneidstation freigeben", "confidence": 0.8},
    ]
    out = attach_belegtext(actions, knowledge, "STO-FOLIE")
    assert all(a.get("beleg_text") for a in out)  # jede Karte trägt einen echten Satz
    assert all(
        not a["beleg_text"].lower().startswith("beleg:") for a in out
    )  # kein „Beleg: Vorfall X"
    assert len({a["beleg_quelle"] for a in out}) == 2  # verschiedene Karten → verschiedene Quellen


def test_attach_belegtext_ohne_dokumente_unveraendert_falsifikation():
    actions = [{"title": "X", "description": "Y", "confidence": 0.8}]
    out = attach_belegtext(actions, [{"event_id": 1}], "STO-FOLIE")  # nur Vorfall, kein Dokument
    assert "beleg_text" not in out[0]  # nichts erfunden


def test_original_passage_loest_ueberschrift_zu_abschnitt():
    heading = "### E-4711 – Folienriss Folienwickler (Priorität 2)"
    passage = _original_passage("MA-02-folienwickler.md", heading)
    assert passage != heading  # nicht nur die Überschrift
    assert "Ursache" in passage or "Maßnahmen" in passage  # echter Abschnittstext aus dem Dokument


_FAKE_LLM = {
    "narrow_cause": RunnableLambda(
        lambda _: _HypothesesOutput(
            candidates=[
                Hypothesis(
                    cause="Folienriss",
                    reason_code="STO-FOLIE",
                    confidence=0.82,
                    evidence=["E-4711"],
                    expected_downtime_min=25.0,
                )
            ]
        )
    ),
    "derive_actions": RunnableLambda(
        lambda _: _ActionsOutput(
            actions=[
                RecommendedAction(
                    title="Folienriss beheben",
                    description="Rolle prüfen und Bahn neu einfädeln.",
                    level=ActionLevel.APPROVAL_REQUIRED,
                    confidence=0.82,
                    rationale="Beleg: ähnlicher Vorfall 7",
                )
            ]
        )
    ),
}


def _tools_mit_doc():
    return {
        "get_line_status": lambda **_: json.dumps(
            [{"equipment_id": "EQ1", "packml_state": "Held", "ts": "2026-01-01 00:00:00"}]
        ),
        "get_production_plan": lambda **_: json.dumps([]),
        "get_active_alarms": lambda **_: json.dumps(
            [{"alarm_code": "E-4711", "ts": "2026-01-01 00:00:00", "priority": 1}]
        ),
        "search_maintenance_docs": lambda **_: json.dumps(
            [{"doc": "MA-02-folienwickler.md", "text": "[Folienwickler] Folienriss: Rolle prüfen."}]
        ),
        "find_similar_incidents": lambda **_: json.dumps(
            [{"event_id": 7, "reason_code": "STO-FOLIE", "duration_min": 12.0}]
        ),
        "estimate_impact": lambda **_: json.dumps(
            {"expected_downtime_min": 25.0, "cost_eur": 5000}
        ),
    }


def test_interrupt_payload_traegt_schwelle_und_beleg():
    g = build_graph(tools=_tools_mit_doc(), llm=_FAKE_LLM)
    last = None
    for update in g.stream(
        {"line_id": "L1", "trace": []},
        {"configurable": {"thread_id": "beleg-int"}},
        stream_mode="updates",
    ):
        last = update
    payload = last["__interrupt__"][0].value
    assert payload.get("applied_threshold") == 0.6  # aktive Schwelle steht im Freigabe-Payload
    actions = payload.get("actions", [])
    assert actions and actions[0].get("beleg_text")  # Maßnahme trägt den Original-Belegtext
    assert "Folienriss" in actions[0]["beleg_text"]  # echter Dokumentsatz durchgereicht
