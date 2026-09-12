"""Selbstcheck des Autopilots: grün auf dem echten Code; erkennt ein fehlendes run.py-Flag (Falsifikation)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "autopilot"))
import selfcheck  # noqa: E402


def test_selfcheck_green_on_real_code():
    assert selfcheck.run() == 0


def test_flags_ok_detects_missing_flag_falsification():
    # Falsifikation: fehlt in run.py ein Flag, das orchestrate.py nutzt, meldet der Selbstcheck es
    assert selfcheck._flags_ok("usage: --only --review", ["--max-loops"]) == ["--max-loops"]
    assert (
        selfcheck._flags_ok("--only --max-loops --extra-prompt", ["--max-loops", "--extra-prompt"])
        == []
    )


def test_check_run_cli_green():
    ok, detail = selfcheck.check_run_cli()
    assert ok, detail


def test_check_quota_and_heal_green():
    assert selfcheck.check_quota()[0]
    assert selfcheck.check_heal()[0]
