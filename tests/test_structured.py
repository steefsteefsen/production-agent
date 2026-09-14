"""Robuste Verarbeitung strukturierter LLM-Ausgaben (graph/structured.py).

Deckt das reale Live-Fehlermuster ab: das Modell liefert die strukturierte Ausgabe als JSON-String
statt als native Liste (ValidationError für _ActionsOutput.actions). Verifikation: der Fix
entschachtelt und liefert das korrekte Objekt. Falsifikation: wirklich kaputtes JSON schlägt SAUBER
fehl (Fehler mit Rohtext), es wird NIE still eine leere Liste zurückgegeben.
"""

import json

import pytest
from pydantic import ValidationError

from production_agent.graph.state import Hypothesis
from production_agent.graph.structured import coerce_structured, invoke_structured
from production_agent.graph.workflow import _ActionsOutput

VALID_ACTION = {
    "title": "Folie neu einlegen",
    "description": "Bewährte Maßnahme aus ähnlichem Vorfall",
    "confidence": 0.7,
    "rationale": "Beleg: ähnlicher Vorfall 358",
}


class _FakeRaw:
    def __init__(self, args):
        self.tool_calls = [{"args": args}]
        self.content = ""


class _Chain:
    def __init__(self, result):
        self._r = result

    def invoke(self, _messages):
        return self._r


def test_coerce_doppelt_kodierter_json_string_verification():
    """Das gesamte Objekt kam als JSON-String im ersten Feld (genau der Live-Fehler)."""
    payload = {"actions": json.dumps({"actions": [VALID_ACTION]})}
    out = coerce_structured(payload, _ActionsOutput)
    assert len(out.actions) == 1 and out.actions[0].title == "Folie neu einlegen"


def test_coerce_reiner_json_string_verification():
    out = coerce_structured(json.dumps({"actions": [VALID_ACTION]}), _ActionsOutput)
    assert len(out.actions) == 1


def test_coerce_nackte_liste_verification():
    out = coerce_structured(json.dumps([VALID_ACTION]), _ActionsOutput)
    assert len(out.actions) == 1


def test_invoke_include_raw_recovery_verification():
    """include_raw-Dict mit parsing_error → Recovery aus raw.tool_calls-args."""
    raw = _FakeRaw({"actions": json.dumps({"actions": [VALID_ACTION]})})
    chain = _Chain({"raw": raw, "parsed": None, "parsing_error": "list_type"})
    out = invoke_structured(chain, [], _ActionsOutput)
    assert len(out.actions) == 1


def test_invoke_parsed_ok_passthrough_verification():
    obj = _ActionsOutput(actions=[])
    chain = _Chain({"raw": None, "parsed": obj, "parsing_error": None})
    assert invoke_structured(chain, [], _ActionsOutput) is obj


def test_invoke_model_instance_passthrough_verification():
    """Mock-/Standardfall: die Chain liefert schon das Zielobjekt."""
    obj = _ActionsOutput(actions=[])
    assert invoke_structured(_Chain(obj), [], _ActionsOutput) is obj


def test_hypothesis_json_string_verification():
    h = coerce_structured(
        json.dumps(
            {
                "cause": "x",
                "reason_code": "STO-FOLIE",
                "confidence": 0.8,
                "expected_downtime_min": 20,
            }
        ),
        Hypothesis,
    )
    assert h.reason_code == "STO-FOLIE"


def test_coerce_kaputtes_json_falsification():
    """Wirklich kaputtes JSON → sauberer Fehler, KEINE leere Liste."""
    with pytest.raises(ValueError):
        coerce_structured("{kaputt: nein", _ActionsOutput)


def test_coerce_strukturell_ungueltig_falsification():
    """Gültiges JSON, aber falsche Struktur → ValidationError, nicht still leer."""
    with pytest.raises(ValidationError):
        coerce_structured({"actions": 5}, _ActionsOutput)
