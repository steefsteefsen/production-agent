"""Beleg-Prüfung (LLM-as-Judge, Knoten 6b): getrennter Kontext, kein Auto-Verwerfen.

Verifikation: ein zitierter Vorfall wird als Beleg gefunden und stützt die Maßnahme.
Falsifikation: ohne belegenden Vorfall bestätigt der Judge NICHT – er lässt sich nicht vom
Maßnahmentext selbst überzeugen.
"""

from production_agent.graph.judge import JudgeVerdict, cited_evidence, judge_action
from production_agent.graph.mock_llm import mock_judge_chain

KNOWLEDGE = [
    {"event_id": 358, "reason_code": "STO-FOLIE", "resolution_action": "Folie neu einlegen"},
    {"title": "Wartungsdokument", "text": "Vorgehen bei Folienriss"},  # Dokument ohne event_id
]


def test_cited_evidence_findet_zitierten_vorfall_verification():
    action = {"title": "X", "rationale": "Beleg: ähnlicher Vorfall 358 (STO-FOLIE)"}
    ev = cited_evidence(action, KNOWLEDGE)
    assert len(ev) == 1 and ev[0]["event_id"] == 358


def test_cited_evidence_ohne_zitat_leer_falsification():
    action = {"title": "X", "rationale": "keine Vorfall-ID genannt"}
    assert cited_evidence(action, KNOWLEDGE) == []


def test_mock_judge_bestaetigt_bei_beleg_verification():
    chain = mock_judge_chain()
    action = {"title": "Folie neu einlegen", "description": "…", "rationale": "Beleg: Vorfall 358"}
    ev = cited_evidence(action, KNOWLEDGE)
    res = judge_action(chain, action, ev)
    assert res["verified"] is True
    assert "358" in res["judge_note"]
    assert res["title"] == "Folie neu einlegen"


def test_mock_judge_lehnt_ohne_beleg_ab_falsification():
    """Ohne belegenden Vorfall (manipuliert/entfernt) darf der Judge nicht bestätigen –
    auch nicht, wenn der Maßnahmentext plausibel klingt."""
    chain = mock_judge_chain()
    action = {"title": "Folie neu einlegen", "description": "klingt plausibel"}
    res = judge_action(chain, action, [])  # Beleg fehlt/entfernt
    assert res["verified"] is False
    assert res["judge_note"]


def test_judge_verdict_schema():
    v = JudgeVerdict(verified=True)
    assert v.verified is True and v.judge_note == ""
