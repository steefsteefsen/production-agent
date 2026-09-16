"""Tests für das deterministische Mock-LLM (LLM_MODE=mock).

Verifikation: narrow_cause leitet den reason_code aus den ähnlichen Vorfällen ab, derive_actions belegt
jede Maßnahme mit einer Vorfall-ID. Falsifikation: ohne Vorfälle im Kontext kann keine Maßnahme belegen.
"""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from production_agent.graph.mock_llm import mock_chains, mock_feedback_completion


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


# --- Rückkopplungs-Vervollständigung: Beispieltext muss zum reason_code passen -------------------
def test_mock_feedback_completion_leitet_beispiel_aus_reason_code_ab():
    """Regression: bei leerer Eingabe (bzw. generischem UI-Default) darf NICHT der STO-FOLIE-Text für
    andere Ursachen erscheinen – der Beispieltext wird aus dem reason_code abgeleitet."""
    default = "Rolle neu eingespannt, nachjustiert"  # generischer Frontend-Default
    antrieb = mock_feedback_completion(default, "STO-ANTRIEB")
    assert "STO-ANTRIEB" in antrieb
    assert "Antriebslager" in antrieb  # fallgerechter Beispieltext
    assert "Rolle neu eingespannt" not in antrieb  # NICHT der STO-FOLIE-Text

    folie = mock_feedback_completion(default, "STO-FOLIE")
    assert "STO-FOLIE" in folie and "Rolle neu eingespannt" in folie
    assert antrieb != folie  # unterschiedliche Fälle → unterschiedlicher Text


def test_mock_feedback_completion_uebernimmt_echte_eingabe_unveraendert():
    """Echte Bedienereingabe bleibt erhalten (nur der generische Default wird ersetzt)."""
    eigen = mock_feedback_completion("Lager getauscht, Fett erneuert", "STO-ANTRIEB")
    assert "Lager getauscht, Fett erneuert" in eigen
    assert "Antriebslager getauscht" not in eigen  # nicht durch Beispiel überschrieben
