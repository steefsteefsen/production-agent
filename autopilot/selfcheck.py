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
        # INF-3 verlangt (D4/D5), dass die erste Commit-Zeile dem obersten AENDERUNGEN.md-Eintrag von HEUTE
        # gleicht. Deshalb schreibt die Probe selbst einen passenden Eintrag – sonst scheitert der commit-msg-Hook.
        import time as _time  # noqa: PLC0415

        probe_title = "chore(autopilot): Selbstcheck-Worktree-Probe"
        entry = (
            f"\n## {_time.strftime('%Y-%m-%d')} · {probe_title}\n"
            "**Was:** Wegwerf-Probe-Commit im Worktree.\n"
            "**Warum (Problem oder Anlass):** Beweist, dass die pre-commit-Kette im Worktree greift.\n"
            "**Alternativen (verworfen, weil ...):** –\n"
            "**Auswirkung (Verträge, ADR, Tests):** –\n"
            "**Bezug (WP, ADR):** SELFCHECK\n"
        )
        ae = wt / "docs" / "AENDERUNGEN.md"
        if ae.exists():
            head_line, _, rest = ae.read_text(encoding="utf-8").partition("\n")
            ae.write_text(head_line + "\n" + entry + rest, encoding="utf-8")
            _git("add", "docs/AENDERUNGEN.md", cwd=wt)
        msg = (
            f"{probe_title}\n\n"
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


def check_rescue_commit_on_hook_failure() -> tuple[bool, str]:
    """journal._commit_or_rescue: scheitert der reguläre Commit an einem Hook (Guardian rot im Worktree),
    MUSS ein Rettungs-Commit OHNE Hooks entstehen und autopilot/logs/commit-fail-<WP>.log geschrieben werden.

    Genau der Nachtlauf-Blocker, bei dem journal.commit den Rückgabewert von git commit nicht prüfte: der
    Commit scheiterte still, run.py meldete trotzdem OK. Deterministisch, in einem Wegwerf-Repo, ohne Modell."""
    if os.environ.get("GIT_INDEX_FILE") or os.environ.get("GIT_DIR"):
        return True, "innerhalb eines git-Hooks – Rettungs-Commit-Probe übersprungen"
    import journal  # noqa: PLC0415

    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    tmp = Path(tempfile.mkdtemp(prefix="selfcheck-rescue-"))
    repo = tmp / "repo"
    repo.mkdir()

    def g(*a: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, env=env)  # noqa: S603, S607

    orig_root = journal.ROOT
    try:
        g("init", "-q")
        g("config", "user.email", "selfcheck@example.invalid")
        g("config", "user.name", "Selfcheck")
        (repo / "a.txt").write_text("erste Fassung\n")
        g("add", "-A")
        g("commit", "-q", "-m", "init")
        base = g("rev-parse", "HEAD").stdout.strip()
        hook = repo / ".git" / "hooks" / "pre-commit"  # Hook, der IMMER scheitert
        hook.write_text("#!/bin/sh\necho 'Hook rot (Selbstcheck-Probe)' 1>&2\nexit 1\n")
        hook.chmod(0o755)
        (repo / "a.txt").write_text("zweite Fassung\n")
        g("add", "-A")
        journal.ROOT = (
            repo  # journal._git/_git_cp und der Fail-Log-Pfad zeigen auf das Wegwerf-Repo
        )
        ok = journal._commit_or_rescue(
            "PROBE", "chore(PROBE): Rettung", "Body", "Gate: grün | Review: pass | Guardian: ok"
        )
        head = g("rev-parse", "HEAD").stdout.strip()
        if not ok or head == base:
            return False, "kein Rettungs-Commit trotz Hook-Fehler"
        if not (repo / "autopilot" / "logs" / "commit-fail-PROBE.log").exists():
            return False, "commit-fail-PROBE.log nicht geschrieben"
        if "hooks: übersprungen" not in g("log", "-1", "--format=%B").stdout:
            return False, "Rettungs-Commit ohne Footer 'hooks: übersprungen'"
        return True, "Hook-Fehler → Rettungs-Commit ohne Hooks + commit-fail-Log geschrieben"
    finally:
        journal.ROOT = orig_root
        shutil.rmtree(tmp, ignore_errors=True)


def check_merge_post_guardian_green() -> tuple[bool, str]:
    """Runner.merge_wp: nach dem Merge ZUERST status.py/present.py --stage + voller Coverage-Lauf, DANN
    Guardian; bei grünem Guardian wird der Strang merged. Genau der Fix für „Guardian rot nach Merge"
    (D6/D7/K4 waren nach dem Merge veraltet). Reihenfolge über einen aufzeichnenden Fake-_sh geprüft."""
    import orchestrate  # noqa: PLC0415

    calls: list[tuple[str, ...]] = []

    class _R:
        returncode = 0
        stdout = "deadbee\n"
        stderr = ""

    class Recording(orchestrate.Runner):
        def _sh(self, *args: str, cwd=orchestrate.ROOT):
            calls.append(args)
            return _R()

    plan = {"lanes": {}, "packages": [{"id": "WP1", "lane": "data", "deps": []}]}
    r = Recording(plan)
    state = orchestrate.init_state(plan, 40.0, "selfcheck")
    state["wp"]["WP1"]["status"] = "review_pass"
    state["wp"]["WP1"]["worktree"] = "orch-WP1-platzhalter"  # Fake-_sh berührt den Pfad nie
    r.merge_wp("WP1", state)
    joined = [" ".join(a) for a in calls]

    def idx(sub: str) -> int:
        return next((i for i, c in enumerate(joined) if sub in c), -1)

    i_merge, i_status = idx("merge --no-ff"), idx("status.py --stage")
    i_present, i_cov, i_guard = (
        idx("present.py --stage"),
        idx("--cov=production_agent"),
        idx("guardian.py"),
    )
    if not (-1 < i_merge < i_status and i_merge < i_present and i_merge < i_cov < i_guard):
        return (
            False,
            f"Reihenfolge falsch: merge={i_merge} status={i_status} present={i_present} cov={i_cov} guard={i_guard}",
        )
    if state["wp"]["WP1"]["status"] != orchestrate.DONE:
        return False, "Guardian grün, aber Strang nicht merged"
    return (
        True,
        "Merge → status/present/Coverage in Merge-Commit gefaltet → Guardian; grün → merged",
    )


CHECKS = [
    ("Imports", check_imports),
    ("run.py-Flags", check_run_cli),
    ("Pipeline (Fake-claude)", check_pipeline),
    ("Quota-429", check_quota),
    ("Heal", check_heal),
    ("Worktree-Commit (echte Hooks)", check_worktree_commit),
    ("Rettungs-Commit bei Hook-Fehler", check_rescue_commit_on_hook_failure),
    ("Merge + Post-Merge-Guardian grün", check_merge_post_guardian_green),
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
