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


def test_claude_timeout_returns_timeout_not_hang_falsification(tmp_path, monkeypatch):
    fake = tmp_path / "claude"
    fake.write_text("#!/usr/bin/env bash\nsleep 30\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    rc, out = run.claude("x", "data-agent", 1, 1.0, tmp_path / "log.txt", timeout=1)
    assert rc == 124 and out == {"timeout": True}
