#!/usr/bin/env python3
"""Selbstcheck des Autopilots: fährt die komplette Kette einmal mit einem deterministischen Fake-claude
(tests/fake_claude.py) durch – Scheduler → Builder → Gate → Reviewer → Decider → Journal → Status →
Präsentation, inklusive Quota-429- und Heal-Fall – OHNE echte Modell-Kosten und ohne den Baum zu verändern.

Zweck: einen kaputten Autopilot (falsches Flag, Importfehler, gebrochene Verdrahtung) VOR dem Nachtlauf
erkennen. Läuft beim Start von orchestrate.py (--no-selfcheck überspringt) und als Guardian-Regel K8 bei
jedem Commit, der autopilot/ berührt. Exit 0 = grün, sonst rot mit Begründung je Prüfung.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "autopilot"))
sys.path.insert(0, str(ROOT / "tests"))

# Flags, die orchestrate.py an run.py übergibt – jedes MUSS run.py --help kennen (falsches Flag = Nachtlauf tot)
REQUIRED_RUN_FLAGS = [
    "--only",
    "--review",
    "--max-loops",
    "--extra-prompt",
    "--no-commit",
    "--api-billing",
]


def _flags_ok(help_text: str, required: list[str]) -> list[str]:
    return [f for f in required if f not in help_text]


def check_imports() -> tuple[bool, str]:
    for mod in (
        "cc",
        "run",
        "reviewer",
        "decider",
        "journal",
        "heal",
        "orchestrate",
        "status",
        "present",
    ):
        try:
            __import__(mod)
        except Exception as e:  # noqa: BLE001 – jeder Importfehler ist ein roter Selbstcheck
            return False, f"Import {mod}: {e}"
    return True, "alle Module importierbar"


def check_run_cli() -> tuple[bool, str]:
    r = subprocess.run(
        [sys.executable, str(ROOT / "autopilot" / "run.py"), "--help"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=60,
    )
    if r.returncode != 0:
        return False, f"run.py --help Exit {r.returncode}: {r.stderr[:200]}"
    missing = _flags_ok(r.stdout, REQUIRED_RUN_FLAGS)
    if missing:
        return False, f"run.py fehlen Flags, die orchestrate.py nutzt: {missing}"
    return True, "run.py kennt alle Orchestrator-Flags"


def check_pipeline() -> tuple[bool, str]:
    import decider
    import heal
    import journal
    import orchestrate

    import fake_claude

    plan = orchestrate.load_plan()
    state = orchestrate.init_state(plan, 40.0, "selfcheck")
    if not orchestrate.startable(state, plan):
        return False, "Scheduler findet kein startbereites Paket"
    rc, cj = fake_claude.builder()
    if rc != 0 or not isinstance(cj, dict):
        return False, "Builder-Fake liefert kein Ergebnis"
    verdict = fake_claude.reviewer_pass()
    if verdict.get("verdict") != "pass":
        return False, "Reviewer-Fake nicht pass"
    if decider.interpret(fake_claude.decide()).get("action") != "apply":
        return False, "Decider-Verdrahtung liefert nicht apply"
    e = journal.entry("SELFCHECK", "qa", 1, True, cj, "grün", 1.0, narrate=False)
    if not isinstance(e, dict):
        return False, "journal.entry ohne Ergebnis"
    if heal.interpret_heal(fake_claude.HEAL).get("action") != "apply":
        return False, "Heal-Verdrahtung liefert nicht apply"
    return True, "Scheduler→Builder→Gate→Reviewer→Decider→Journal→Heal verdrahtet"


def check_quota() -> tuple[bool, str]:
    import cc

    err = '{"is_error": true, "api_error_status": "429", "result": "rate limit"}'
    ok = '{"is_error": false, "result": "usage limit im Text ist ok"}'
    if not cc.is_quota(1, err):
        return False, "429-Fehler wird NICHT als Quota erkannt"
    if cc.is_quota(0, ok):
        return False, "erfolgreiche Antwort wird fälschlich als Quota erkannt"
    return True, "Quota-429 erkannt, Fehlalarm ausgeschlossen"


def check_heal() -> tuple[bool, str]:
    import heal

    if (
        heal.interpret_heal({"needs_spec_change": False, "fix_prompt": "ergänze Import"})["action"]
        != "apply"
    ):
        return False, "gültiger Fix wird nicht angewendet"
    bad = heal.interpret_heal(
        {"needs_spec_change": False, "fix_prompt": "ändere tests/acceptance/test_wp1.py"}
    )
    if bad["action"] != "escalate":
        return False, "Fix, der Abnahmetests ändert, wird nicht verworfen"
    return True, "Heal wendet gültige Fixes an, verwirft Spec-Eingriffe"


CHECKS = [
    ("Imports", check_imports),
    ("run.py-Flags", check_run_cli),
    ("Pipeline (Fake-claude)", check_pipeline),
    ("Quota-429", check_quota),
    ("Heal", check_heal),
]


def run() -> int:
    failed = 0
    for name, fn in CHECKS:
        try:
            ok, detail = fn()
        except Exception as e:  # noqa: BLE001
            ok, detail = False, f"Ausnahme: {e}"
        print(f"[{'ok ' if ok else 'ROT'}] {name}: {detail}")
        failed += not ok
    print(f"\nSelbstcheck {'grün' if not failed else f'ROT ({failed} Fehler)'}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(run())
