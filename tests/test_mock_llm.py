"""Tests für das deterministische Mock-LLM (LLM_MODE=mock).

Verifikation: narrow_cause leitet den reason_code aus den ähnlichen Vorfällen ab, derive_actions belegt
jede Maßnahme mit einer Vorfall-ID. Falsifikation: ohne Vorfälle im Kontext kann keine Maßnahme belegen.
"""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from production_agent.graph.mock_llm import mock_chains


def _msgs(ctx: dict):
    return [SystemMessage(content="sys"), HumanMessage(content="Kontext:\n" + json.dumps(ctx))]


def test_mock_narrow_cause_leitet_reason_code_aus_vorfaellen_ab():
    ctx = {
        "alarms": [{"alarm_code": "E-4711", "ts": "2026-08-28 07:18:44"}],
        "knowledge": [{"event_id": "7", "reason_code": "STO-FOLIE", "duration_min": 20}],
    }
    out = mock_chains()["narrow_cause"].invoke(_msgs(ctx))
    assert len(out.candidates) >= 1  # Knoten 4 liefert mehrere Kandidaten
    hyp = out.candidates[0]  # beste zuerst
    assert hyp.reason_code == "STO-FOLIE"
    assert "E-4711" in hyp.evidence  # Erstalarm als Evidenz
    assert any("7" == e for e in hyp.evidence)  # Vorfall-ID als Evidenz


def test_mock_derive_actions_belegt_jede_massnahme_mit_vorfall_id():
    ctx = {
        "hypothesis": {"reason_code": "STO-FOLIE", "confidence": 0.8},
        "knowledge": [{"event_id": "7", "reason_code": "STO-FOLIE"}],
    }
    out = mock_chains()["derive_actions"].invoke(_msgs(ctx))
    assert len(out.actions) >= 1
    assert all("7" in a.rationale for a in out.actions)


def test_mock_derive_actions_ohne_vorfaelle_belegt_nicht_falsification():
    """Falsifikation: ohne Vorfälle im Kontext trägt keine Maßnahme eine Vorfall-ID (die Nachbedingung
    in Knoten 6 würde solche Maßnahmen später verwerfen)."""
    ctx = {
        "hypothesis": {"reason_code": "X", "confidence": 0.8},
        "knowledge": [{"chunk_id": "d#0", "text": "nur ein Dokument"}],
    }
    out = mock_chains()["derive_actions"].invoke(_msgs(ctx))
    assert out.actions  # es werden Maßnahmen erzeugt …
    assert all(a.rationale == "keine Vorfall-ID verfügbar" for a in out.actions)  # … aber unbelegt
