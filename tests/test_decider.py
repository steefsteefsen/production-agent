"""Auto-Decider: reine interpret-Logik – Risiko und decisions.yaml-Konflikt entscheiden."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "autopilot"))

import decider  # noqa: E402


def test_low_risk_no_conflict_is_applied():
    r = decider.interpret({"risk": "low", "changes_decisions": False, "decision": "weiter"})
    assert r["action"] == "apply" and "prüfen" in r["note"]


def test_high_risk_escalates_falsification():
    r = decider.interpret({"risk": "high", "changes_decisions": False, "decision": "Not-Aus"})
    assert r["action"] == "escalate"


def test_decision_against_decisions_yaml_is_rejected_falsification():
    r = decider.interpret({"risk": "low", "changes_decisions": True, "decision": "Schwelle 0.9"})
    assert r["action"] == "reject"
