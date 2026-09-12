import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "autopilot"))
import commit_check  # noqa: E402

GOOD = "feat(WP2a): sechs Werkzeuge\n\nGebaut: x\n\nGate: grün | Review: pass | Guardian: ok\n"


def test_valid_message_passes():
    assert commit_check.check(GOOD) == []


def test_missing_scope_and_footer_fail_falsification():
    assert len(commit_check.check("update stuff")) == 2
    assert commit_check.check(
        "feat(WP1): " + "x" * 80 + "\n\nGate: grün | Review: pass | Guardian: ok"
    )
    assert commit_check.check("feat(WP1): ok\n\nkein footer")


def test_title_length_limit_is_72_falsification():
    footer = "\n\nGate: grün | Review: pass | Guardian: ok"
    too_long = "feat(WP1): " + "x" * (73 - len("feat(WP1): "))  # erste Zeile = 73 Zeichen
    assert any("72" in e for e in commit_check.check(too_long + footer))
    exact = "feat(WP1): " + "x" * (72 - len("feat(WP1): "))  # erste Zeile = 72 Zeichen
    assert commit_check.check(exact + footer) == []
