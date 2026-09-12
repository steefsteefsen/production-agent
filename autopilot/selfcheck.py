#!/usr/bin/env python3
"""Selbstcheck des Autopilots: fährt die komplette Kette einmal mit einem deterministischen Fake-claude
(tests/fake_claude.py) durch – Scheduler → Builder → Gate → Reviewer → Decider → Journal → Status →
Präsentation, inklusive Quota-429- und Heal-Fall – OHNE echte Modell-Kosten und ohne den Baum zu verändern.

Zweck: einen kaputten Autopilot (falsches Flag, Importfehler, gebrochene Verdrahtung) VOR dem Nachtlauf
erkennen. Läuft beim Start von orchestrate.py (--no-selfcheck überspringt) und als Guardian-Regel K8 bei
jedem Commit, der autopilot/ berührt. Exit 0 = grün, sonst rot mit Begründung je Prüfung.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
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
    if not callable(getattr(cc, "probe", None)):
        return False, "cc.probe fehlt – keine aktive Quota-Wiederaufnahme je Wartrunde"
    return True, "Quota-429 erkannt, Fehlalarm ausgeschlossen, cc.probe vorhanden"


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


def _git(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)  # noqa: S603, S607


def check_worktree_commit() -> tuple[bool, str]:
    """Echter git worktree + echter pre-commit-Lauf: beweist, dass ein Builder-Commit im Worktree durchläuft.

    Stellt die beiden Nachtlauf-Blocker nach: (B1) der .venv-Symlink löst die Hook-Befehle (.venv/bin/python)
    im Worktree auf; (B3) der Commit läuft ohne „files were modified by this hook"-Schleife durch (Guardian K2
    formatiert nicht mehr, der Committer formatiert vorher). Ohne echtes Modell – nur git + Hooks.
    GUARDIAN_SKIP_K8=1 im Kind-Commit verhindert eine Selbstcheck-Rekursion."""
    if os.environ.get("GIT_INDEX_FILE") or os.environ.get("GIT_DIR"):
        # Selbstcheck läuft innerhalb eines git-Hooks (z. B. Guardian K8 im pre-commit): keine
        # verschachtelten git-Operationen am selben Repo, sonst bricht der laufende Commit am Index.
        return (
            True,
            "innerhalb eines git-Hooks – Worktree-Commit-Probe übersprungen (kein Nested-Commit)",
        )
    if not (ROOT / ".venv" / "bin" / "python").exists():
        return True, "kein .venv im Hauptbaum – Worktree-Commit-Probe übersprungen"
    _git("worktree", "prune")  # verwaiste Registrierungen eines früheren Laufs entfernen
    tmp = Path(tempfile.mkdtemp(prefix="selfcheck-wt-"))
    wt = tmp / "wt"
    branch = f"selfcheck/worktree-probe-{os.getpid()}"  # eindeutig: keine Kollision mit Altläufen
    base = _git("rev-parse", "HEAD").stdout.strip()
    try:
        r = _git("worktree", "add", "-B", branch, str(wt), "HEAD")
        if r.returncode != 0:
            return False, f"git worktree add scheitert: {(r.stdout + r.stderr)[-200:].strip()}"
        (wt / ".venv").symlink_to(ROOT / ".venv")  # B1-Fix wie in orchestrate.py nachstellen
        if (ROOT / ".env").exists():
            (wt / ".env").write_bytes((ROOT / ".env").read_bytes())
        if (ROOT / ".guardian").exists():  # Stempel/Coverage mitgeben → K4 ohne vollen pytest-Lauf
            shutil.copytree(ROOT / ".guardian", wt / ".guardian", dirs_exist_ok=True)
            cov = wt / ".guardian" / "coverage.json"
            if cov.exists():
                os.utime(cov, None)  # frisch stempeln, sonst läuft im Worktree pytest --cov
        # guardian-neutrale Builder-Änderung (kein .md/src/autopilot-Python): eine Datei im Hauptverzeichnis
        (wt / ".selfcheck-worktree-probe").write_text("Worktree-Commit-Probe des Selbstchecks.\n")
        _git("add", ".selfcheck-worktree-probe", cwd=wt)
        msg = (
            "chore(autopilot): Selbstcheck-Worktree-Probe\n\n"
            "Gebaut: Probe-Commit. Getestet: pre-commit im Worktree. Offen: keine.\n\n"
            "Gate: grün | Review: pass | Guardian: ok\n"
        )
        env = {**os.environ, "GUARDIAN_SKIP_K8": "1"}  # keine Selbstcheck-Rekursion im Kind-Commit
        c = subprocess.run(  # noqa: S603, S607
            ["git", "commit", "-m", msg], cwd=wt, capture_output=True, text=True, env=env
        )
        head = _git("rev-parse", "HEAD", cwd=wt).stdout.strip()
        if c.returncode != 0 or head == base:
            return False, f"Commit im Worktree scheitert: {(c.stdout + c.stderr)[-400:].strip()}"
        return (
            True,
            "Worktree-Commit mit echten pre-commit-Hooks durchgelaufen (.venv-Symlink, keine Format-Schleife)",
        )
    finally:
        _git("worktree", "remove", "--force", str(wt))
        _git("branch", "-D", branch)
        _git("worktree", "prune")
        shutil.rmtree(tmp, ignore_errors=True)


CHECKS = [
    ("Imports", check_imports),
    ("run.py-Flags", check_run_cli),
    ("Pipeline (Fake-claude)", check_pipeline),
    ("Quota-429", check_quota),
    ("Heal", check_heal),
    ("Worktree-Commit (echte Hooks)", check_worktree_commit),
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
