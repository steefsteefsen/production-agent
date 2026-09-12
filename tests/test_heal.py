"""Heal-Auswertung: gültige Fixes werden angewendet, Eingriffe in die Spezifikation/Sicherheit verworfen."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "autopilot"))
import heal  # noqa: E402


def test_interpret_apply_valid_fix():
    r = heal.interpret_heal(
        {"needs_spec_change": False, "fix_prompt": "ergänze den fehlenden Import"}
    )
    assert r["action"] == "apply"


def test_interpret_rejects_acceptance_change_falsification():
    # Falsifikation: ein Fixer, der die Abnahmetests umschreiben will, wird verworfen und eskaliert
    r = heal.interpret_heal(
        {
            "needs_spec_change": False,
            "fix_prompt": "Ändere tests/acceptance/test_wp1.py, bis es grün wird",
        }
    )
    assert r["action"] == "escalate"


def test_interpret_rejects_decisions_change():
    r = heal.interpret_heal(
        {"needs_spec_change": False, "fix_prompt": "passe decisions.yaml an das Ergebnis an"}
    )
    assert r["action"] == "escalate"


def test_interpret_escalates_on_needs_spec_change():
    r = heal.interpret_heal({"needs_spec_change": True, "fix_prompt": "x", "question": "Darf X?"})
    assert r["action"] == "escalate"


def test_interpret_escalates_without_fix_prompt():
    assert (
        heal.interpret_heal({"needs_spec_change": False, "fix_prompt": ""})["action"] == "escalate"
    )
