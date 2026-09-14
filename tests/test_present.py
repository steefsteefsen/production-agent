"""Präsentation: aus Commits/Journal entsteht HTML mit parsebarem JSON und sechs Tabs."""

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "autopilot"))

import journal  # noqa: E402
import present  # noqa: E402


def test_classify_scope_and_sonstige_falsification():
    assert present.classify("feat(WP1): x") == ("feat", "WP1")
    assert present.classify("irgendein Commit ohne Konvention") == ("sonstige", "")


def test_build_and_render_has_all_tabs_and_all_commits():
    commits = [
        {
            "sha": "a1b2c3d",
            "at": "2026-09-11T10:00:00",
            "title": "feat(WP1): x",
            "type": "feat",
            "scope": "WP1",
            "body": "",
        },
        {
            "sha": "e4f5a6b",
            "at": "2026-09-12T10:00:00",
            "title": "sonstiges",
            "type": "sonstige",
            "scope": "",
            "body": "",
        },
    ]
    data = present.build_presentation(commits, [], None, {"total": 92, "security": 100}, [], [])
    html = present.render_html(data)
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
    parsed = json.loads(m.group(1))
    assert len(parsed["commits"]) == 2
    assert len(present.TABS) == 9
    for key, _label in present.TABS:
        assert f'data-tab="{key}"' in html
    # kuratierte Panels: Daten vorhanden und im HTML sichtbar
    assert {"scope", "technik", "grenzen"} <= {k for k, _ in present.TABS}
    assert parsed["scope"]["rows"] and parsed["guarantees"]["items"]
    assert parsed["stack"]["rows"] and len(parsed["stack"]["columns"]) == 3
    assert "Kein ML-Training" in html
    assert "Scope spart man vor dem Kauf" in html
    # Technologie-Entscheidungen mit ehrlichem Retrieval-Befund
    assert "Technologie-Entscheidungen" in html
    assert "LLM-as-Judge" in html and "BM25" in html


def test_broken_journal_raises_falsification(tmp_path, monkeypatch):
    monkeypatch.setattr(journal, "JOURNAL_DIR", tmp_path)
    monkeypatch.setattr(journal, "JOURNAL_JSON", tmp_path / "nicht_vorhanden.json")
    (tmp_path / "WP1.json").write_text("{kaputt", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        journal.load_all()
