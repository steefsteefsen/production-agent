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
