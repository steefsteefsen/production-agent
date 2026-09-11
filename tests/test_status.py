"""Projektstatus und Doku-Marker: Fortschrittsberechnung, HTML-Einbettung, Guardian-Marker-Regeln."""

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "autopilot"))

import guardian  # noqa: E402
import status  # noqa: E402


def _task(**kw):
    base = {"id": "WP1", "agent": "a", "group": 1}
    base.update(kw)
    return base


def test_percent_progression():
    tasks = [_task()]
    assert status.compute_packages(tasks, [], [], set(), set(), {})[0]["percent"] == 0
    gate = [{"wp": "WP1", "ok": True}]
    assert status.compute_packages(tasks, gate, [], set(), set(), {})[0]["percent"] == 40
    rev = [{"wp": "WP1", "ok": True, "review": {"verdict": "pass"}}]
    assert status.compute_packages(tasks, rev, [], set(), set(), {})[0]["percent"] == 70
    commits = [
        {"sha": "abcdef1", "title": "feat(WP1): x", "at": "2026-09-11T10:00:00", "scope": "WP1"}
    ]
    assert status.compute_packages(tasks, rev, commits, set(), set(), {})[0]["percent"] == 90
    assert status.compute_packages(tasks, rev, commits, {"WP1"}, set(), {})[0]["percent"] == 100


def test_html_embeds_parsable_json():
    pkgs = status.compute_packages([_task()], [], [], set(), set(), {})
    st = status.build_status(packages=pkgs, commit="", branch="main")
    html = status.render_html(st)
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
    assert m and json.loads(m.group(1))["packages"][0]["id"] == "WP1"


def test_markers_round_trip_green():
    """Verifikation: nach Füllung stimmt der Marker mit dem Wert (D7 grün)."""
    vals = {"tests": "34", "stand": "- fertig: 3\n- offen: X"}
    text = status.apply_markers(
        "Tests <!-- auto:tests -->0<!-- /auto:tests -->\n"
        "## Stand\n<!-- auto:stand -->\nalt\n<!-- /auto:stand -->\n",
        vals,
    )
    assert "34" in text
    assert guardian.check_markers({"x.md": text}, vals) == []


def test_review_fail_without_pass_is_blocked_falsification():
    j = [{"wp": "WP1", "ok": True, "review": {"verdict": "fail"}}]
    assert status.compute_packages([_task()], j, [], set(), set(), {})[0]["state"] == "blockiert"


def test_broken_journal_raises_falsification(tmp_path):
    bad = tmp_path / "journal.json"
    bad.write_text("{kaputt", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        status.load_journal_file(bad)


def test_typed_number_outside_marker_is_d8_red_falsification():
    errs = guardian.check_doc_facts({"README.md": "Das Projekt hat 16 Tests im Kern."})
    assert any("D8" in e for e in errs)


def test_marker_wrong_value_is_d7_red_falsification():
    files = {"README.md": "<!-- auto:tests -->999<!-- /auto:tests -->"}
    assert any("D7" in e for e in guardian.check_markers(files, {"tests": "34"}))


def test_precommit_entry_without_venv_is_k5_red_falsification():
    text = "      - id: x\n        entry: python autopilot/guardian.py\n"
    assert any("K5" in e for e in guardian.check_precommit_entries(text))
