"""run.py-CLI: --max-loops vorhanden, unbekanntes Flag scheitert, claude-Timeout hängt nicht."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "autopilot"))

import run  # noqa: E402


def test_max_loops_in_help():
    r = subprocess.run(
        [sys.executable, "autopilot/run.py", "--help"], cwd=ROOT, capture_output=True, text=True
    )
    assert r.returncode == 0 and "--max-loops" in r.stdout


def test_unknown_flag_is_exit_2_falsification():
    r = subprocess.run(
        [sys.executable, "autopilot/run.py", "--gibtsnicht"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 2


def test_green_gate_logs_review_start_quickly_falsification(tmp_path, monkeypatch):
    import time

    monkeypatch.setattr(run, "LOGS", tmp_path)
    monkeypatch.setattr(run, "STATUS", tmp_path / "status.json")
    monkeypatch.setattr(run.cc, "preflight", lambda *a, **k: (True, "ok"))
    monkeypatch.setattr(run, "claude", lambda *a, **k: (0, {"result": "ok"}))
    monkeypatch.setattr(run, "gate", lambda *a, **k: (0, "grün"))
    called = {}

    def fake_review(*a, **k):
        called["at"] = time.time()
        return {"verdict": "pass"}

    monkeypatch.setattr(run.reviewer, "review", fake_review)
    monkeypatch.setattr(
        run.journal,
        "entry",
        lambda *a, **k: {"wp": "WP1", "ok": True, "agent_summary": "x", "files": []},
    )
    monkeypatch.setattr(run.journal, "write", lambda e: None)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run.py", "--only", "WP1", "--review", "auto", "--no-commit", "--max-loops", "1"],
    )
    t0 = time.time()
    run.main()
    log = (tmp_path / "WP1.log").read_text(encoding="utf-8")
    assert "review: start" in log
    assert called.get("at", t0 + 999) - t0 < 2


def test_claude_timeout_returns_timeout_not_hang_falsification(tmp_path, monkeypatch):
    fake = tmp_path / "claude"
    fake.write_text("#!/usr/bin/env bash\nsleep 30\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    rc, out = run.claude("x", "data-agent", 1, 1.0, tmp_path / "log.txt", timeout=1)
    assert rc == 124 and out == {"timeout": True}
