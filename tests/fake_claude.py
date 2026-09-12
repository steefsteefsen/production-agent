"""Deterministischer Ersatz für die claude-CLI im Selbstcheck (autopilot/selfcheck.py).

Zwei Nutzungsarten:
 - als Modul: liefert für Builder/Reviewer/Decider/Heal feste JSON-Antworten (in-process gemockt);
 - als Skript (`python tests/fake_claude.py …`): liest die claude-Flags, gibt eine passende JSON-Antwort
   auf stdout aus und lehnt UNBEKANNTE Flags mit Exit 2 ab – so fällt ein falsches Flag in run.py auf.
"""

from __future__ import annotations

import json
import sys

# Flags, die run.py/reviewer.py/heal.py an claude übergeben dürfen; ein anderes Flag ist ein Fehler.
KNOWN_FLAGS = {
    "-p",
    "--model",
    "--append-system-prompt",
    "--permission-mode",
    "--allowedTools",
    "--max-turns",
    "--output-format",
    "--json-schema",
    "--max-budget-usd",
    "--version",
    "auth",
    "status",
}

BUILDER = {
    "type": "result",
    "is_error": False,
    "result": "fertig",
    "num_turns": 3,
    "total_cost_usd": None,
    "structured_output": None,
}
REVIEWER = {
    "verdict": "pass",
    "items": [
        {"check": "Abnahmetest grün", "result": "pass", "evidence": "pytest", "severity": "low"}
    ],
    "summary": "in Ordnung",
}
DECIDER = {"action": "apply", "risk": "low", "reason": "kein Sicherheitsbezug"}
HEAL = {
    "cause": "fehlender Import",
    "fix_prompt": "ergänze den Import in module.py",
    "needs_spec_change": False,
    "question": "",
}


def builder(*_a, **_k) -> tuple[int, dict]:
    return 0, {**BUILDER}


def reviewer_pass(*_a, **_k) -> dict:
    return {**REVIEWER, "_cost_usd": None}


def decide(*_a, **_k) -> dict:
    return {**DECIDER}


def _response_for(args: list[str]) -> dict:
    blob = " ".join(args).lower()
    if "--json-schema" in args and "verdict" in blob:
        return {
            "type": "result",
            "is_error": False,
            "structured_output": REVIEWER,
            "result": json.dumps(REVIEWER),
            "total_cost_usd": None,
        }
    if "fixer" in blob or "fix_prompt" in blob:
        return {
            "type": "result",
            "is_error": False,
            "structured_output": HEAL,
            "result": json.dumps(HEAL),
            "total_cost_usd": None,
        }
    return {**BUILDER}


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    unknown = [a for a in argv if a.startswith("-") and a not in KNOWN_FLAGS]
    if unknown:
        print(f"fake_claude: unbekanntes Flag {unknown}", file=sys.stderr)
        return 2
    print(json.dumps(_response_for(argv), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
