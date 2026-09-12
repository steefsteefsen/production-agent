#!/usr/bin/env python3
"""Auto-Decider: entscheidet bei einer Rückfrage kontextarm, ob der Orchestrator weiterlaufen darf.

Kontext ausschließlich: decisions.yaml, CLAUDE.md, die Reviewer-Frage, die Gate-Ausgabe, die WP-Spezifikation.
Ausgabe JSON {decision, rationale, risk, changes_decisions}. Regeln (rein, testbar in `interpret`):
  risk == high            → echte Eskalation (Mensch entscheidet)
  changes_decisions       → verworfen (widerspricht decisions.yaml, das nur Stefan ändert)
  sonst                   → anwenden, Zusatz an den Prompt + Notiz "Automatisch entschieden – bitte prüfen"
Der claude-Aufruf läuft mit stdin=DEVNULL und Timeout; bei Timeout/unlesbar → Eskalation.
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
        "decision": {"type": "string"},
        "rationale": {"type": "string"},
        "risk": {"type": "string", "enum": ["low", "medium", "high"]},
        "changes_decisions": {"type": "boolean"},
    },
    "required": ["decision", "rationale", "risk", "changes_decisions"],
}

SYSTEM = (
    "Du entscheidest eng begrenzt, ob ein Arbeitspaket ohne Rückfrage weiterlaufen darf. Kontext sind nur "
    "decisions.yaml, CLAUDE.md, die Reviewer-Frage, die Gate-Ausgabe und die WP-Spezifikation. Du änderst "
    "decisions.yaml nie; wenn deine Entscheidung eine dort festgelegte Zahl, Regel oder Rolle verändern würde, "
    "setze changes_decisions=true und risk=high. Sicherheitsrelevantes ist immer risk=high. Antworte nur im "
    "JSON-Schema."
)


def interpret(result: dict) -> dict:
    """Reine Auswertung der Decider-Antwort → action ∈ escalate|reject|apply."""
    if result.get("risk") == "high":
        return {"action": "escalate", "reason": "Risiko hoch – Mensch entscheidet", **result}
    if result.get("changes_decisions"):
        return {"action": "reject", "reason": "Entscheidung widerspricht decisions.yaml", **result}
    return {
        "action": "apply",
        "note": "Automatisch entschieden – bitte prüfen",
        **result,
    }


def decide(
    wp: str, question: str, gate_tail: str, spec: str, model: str | None = None, timeout: int = 600
) -> dict:
    model = model or cc.model("decider")
    context = (
        f"# WP {wp}\n## Reviewer-Frage / Anlass\n{question}\n\n## Gate-Ausgabe\n{gate_tail[:2000]}\n\n"
        f"## WP-Spezifikation\n{spec[:2000]}\n\n## decisions.yaml\n"
        + (ROOT / "decisions.yaml").read_text(encoding="utf-8")[:6000]
    )
    cmd = [
        "claude",
        "-p",
        context,
        "--model",
        model,
        "--append-system-prompt",
        SYSTEM,
        "--permission-mode",
        "dontAsk",
        "--allowedTools",
        "Read,Grep",
        "--max-turns",
        "10",
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
        return {"action": "escalate", "reason": "Decider-Timeout", "risk": "high"}
    try:
        out = json.loads(p.stdout)
        result = out.get("structured_output") or json.loads(out.get("result", "{}"))
    except (json.JSONDecodeError, TypeError):
        return {"action": "escalate", "reason": "Decider-Antwort unlesbar", "risk": "high"}
    return interpret(result)


if __name__ == "__main__":
    print(json.dumps(decide(*(sys.argv[1:5] + ["", "", ""])[:4]), ensure_ascii=False, indent=2))
