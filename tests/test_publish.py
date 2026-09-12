"""publish.build_message erzeugt eine konforme Commit-Message (Titel ≤ 72, korrekter Footer)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "autopilot"))
import commit_check  # noqa: E402
import publish  # noqa: E402


def test_build_message_is_convention_conform():
    msg = publish.build_message(
        "fix(infra): Selbstheilung, Selbstcheck und Rechte-Lernen",
        "Gebaut: heal/selfcheck. Getestet: pytest grün. Offen: –. Warum: Nachtlauf.",
        gate="grün",
        review="human",
    )
    assert commit_check.check(msg) == []


def test_build_message_footer_present():
    msg = publish.build_message("chore(infra): x", "", gate="grün", review="pass")
    assert "Gate: grün | Review: pass | Guardian: ok" in msg


def test_overlong_title_is_rejected_falsification():
    long_title = "fix(infra): " + "x" * 80
    assert commit_check.check(publish.build_message(long_title, "y"))
