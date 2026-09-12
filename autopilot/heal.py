"""Selbstheilung (--heal): bei erschöpftem Strang oder zweimal Reviewer-fail schlägt ein kontextfreier
Fixer (Sonnet) eine Ursache und einen konkreten Nachbesserungs-Prompt vor – der zum grünen Gate führt,
OHNE Abnahmetests, decisions.yaml oder Sicherheitsregeln anzutasten. Andernfalls Eskalation.

Ausgabe JSON {cause, fix_prompt, needs_spec_change, question}. Reine Auswertung in interpret_heal():
  needs_spec_change true              → Eskalation (Decider/Mensch entscheidet über die Spezifikation)
  fix_prompt fasst Abnahmetests/      → verworfen + Eskalation (der Builder darf die Prüfung nicht umschreiben)
    decisions.yaml/Sicherheit an
  sonst                               → anwenden (neuer Loop-Block mit fix_prompt)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cc  # noqa: E402

SCHEMA = {
    "type": "object",
    "properties": {
        "cause": {"type": "string"},
        "fix_prompt": {"type": "string"},
        "needs_spec_change": {"type": "boolean"},
        "question": {"type": "string"},
    },
    "required": ["cause", "fix_prompt", "needs_spec_change"],
}
SYSTEM = (
    "Du bist ein Fixer für ein erschöpftes Arbeitspaket. Benenne die Ursache und formuliere einen konkreten "
    "Nachbesserungs-Prompt, der das Gate grün macht. Du darfst die Abnahmetests (tests/acceptance/), "
    "decisions.yaml und die Sicherheitsregeln NICHT ändern – wenn nur eine solche Änderung helfen würde, setze "
    "needs_spec_change=true und stelle die Frage. Antworte nur im JSON-Schema."
)
# Signale, dass der Vorschlag die unveränderliche Spezifikation/Sicherheit anfassen will
_FORBIDDEN = (
    "tests/acceptance",
    "decisions.yaml",
    "guardian",
    "action_policy",
    "sql_guard",
    "injection_guard",
    "sicherheitsregel",
    "acceptance test",
    "abnahmetest",
)


def interpret_heal(result: dict) -> dict:
    """Reine Auswertung der Fixer-Antwort → action ∈ escalate|apply."""
    if result.get("needs_spec_change"):
        return {"action": "escalate", "reason": "Fixer verlangt Spezifikationsänderung", **result}
    fp = (result.get("fix_prompt") or "").lower()
    if not fp.strip():
        return {"action": "escalate", "reason": "kein Fix-Prompt", **result}
    if any(t in fp for t in _FORBIDDEN):
        return {
            "action": "escalate",
            "reason": "Fixer will Abnahmetests/Entscheidungen/Sicherheit ändern – verworfen",
            **result,
        }
    return {"action": "apply", **result}


def heal(
    wp: str, spec: str, gate_tail: str, complaints: str, diff: str, timeout: int = 600
) -> dict:
    context = (
        f"# Fixer für {wp}\n## Spezifikation\n{spec[:3000]}\n\n## Letzte Gate-Ausgabe\n{gate_tail[:2000]}\n\n"
        f"## Reviewer-Beanstandungen\n{complaints[:1500]}\n\n## Diff des Worktrees\n{diff[:6000]}\n"
    )
    cmd = [
        "claude",
        "-p",
        context,
        "--model",
        cc.model("builder"),
        "--append-system-prompt",
        SYSTEM,
        "--permission-mode",
        "dontAsk",
        "--allowedTools",
        "Read,Grep,Glob",
        "--max-turns",
        "12",
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(SCHEMA),
    ]
    try:
        p = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
            env=cc.env(),
        )
    except subprocess.TimeoutExpired:
        return {"action": "escalate", "reason": "Fixer-Timeout", "needs_spec_change": False}
    result = cc._last_json(p.stdout)
    if isinstance(result, dict) and "structured_output" in result:
        result = result["structured_output"]
    if not isinstance(result, dict) or "fix_prompt" not in result:
        return {
            "action": "escalate",
            "reason": "Fixer-Antwort unlesbar",
            "needs_spec_change": False,
        }
    return interpret_heal(result)
