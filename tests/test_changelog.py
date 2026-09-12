"""tests/test_changelog.py: Prüft das AENDERUNGEN.md-Änderungsprotokoll (Guardian D4/D5)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "autopilot"))
from guardian import check_changelog  # noqa: E402

TODAY = "2026-09-12"
TITLE = "feat(INF-3): Änderungsprotokoll mit Begründungspflicht eingeführt"

VALID_CL = (
    "# Änderungen\n\n"
    f"## {TODAY} · {TITLE}\n"
    "**Was:** Changelog eingeführt\n"
    "**Warum (Problem oder Anlass):** Begründungspflicht fehlte\n"
    "**Alternativen (verworfen, weil ...):** Freitext – verworfen\n"
    "**Auswirkung (Verträge, ADR, Tests):** Guardian D4/D5 neu\n"
    f"**Bezug (WP, ADR):** INF-3\n"
)

ALL_FILES = ["src/production_agent/foo.py", "docs/AENDERUNGEN.md"]


def test_valid_entry_passes():
    assert check_changelog(ALL_FILES, VALID_CL, TITLE, TODAY) == []


def test_valid_without_commit_title_passes():
    assert check_changelog(ALL_FILES, VALID_CL, None, TODAY) == []


def test_only_aenderungen_staged_no_source_change_passes():
    assert check_changelog(["docs/AENDERUNGEN.md"], VALID_CL, TITLE, TODAY) == []


def test_old_date_fails_falsification():
    old = VALID_CL.replace(TODAY, "2020-01-01")
    errs = check_changelog(ALL_FILES, old, TITLE, TODAY)
    assert any("D4" in e and TODAY in e for e in errs)


def test_missing_was_field_fails_falsification():
    missing = VALID_CL.replace("**Was:**", "**Inhalt:**")
    errs = check_changelog(ALL_FILES, missing, TITLE, TODAY)
    assert any("**Was:**" in e for e in errs)


def test_missing_warum_field_fails_falsification():
    missing = VALID_CL.replace("**Warum (Problem oder Anlass):**", "**Grund:**")
    errs = check_changelog(ALL_FILES, missing, TITLE, TODAY)
    assert any("Warum" in e for e in errs)


def test_missing_alternativen_field_fails_falsification():
    missing = VALID_CL.replace("**Alternativen (verworfen, weil ...):**", "**Alt:**")
    errs = check_changelog(ALL_FILES, missing, TITLE, TODAY)
    assert any("Alternativen" in e for e in errs)


def test_missing_auswirkung_field_fails_falsification():
    missing = VALID_CL.replace("**Auswirkung (Verträge, ADR, Tests):**", "**Wirkung:**")
    errs = check_changelog(ALL_FILES, missing, TITLE, TODAY)
    assert any("Auswirkung" in e for e in errs)


def test_missing_bezug_field_fails_falsification():
    missing = VALID_CL.replace("**Bezug (WP, ADR):**", "**Ref:**")
    errs = check_changelog(ALL_FILES, missing, TITLE, TODAY)
    assert any("Bezug" in e for e in errs)


def test_placeholder_fails_falsification():
    with_ph = VALID_CL.replace("fehlte", "{{TODO}}")
    errs = check_changelog(ALL_FILES, with_ph, TITLE, TODAY)
    assert any("D4" in e and "Platzhalter" in e for e in errs)


def test_title_mismatch_fails_falsification():
    errs = check_changelog(ALL_FILES, VALID_CL, "feat(INF-3): anderer Titel", TODAY)
    assert any("D5" in e for e in errs)


def test_changelog_not_staged_with_src_fails_falsification():
    errs = check_changelog(["src/production_agent/foo.py"], VALID_CL, TITLE, TODAY)
    assert any("D4" in e and "gestaged" in e for e in errs)


def test_empty_changelog_fails_falsification():
    errs = check_changelog(ALL_FILES, "", TITLE, TODAY)
    assert any("D4" in e for e in errs)
