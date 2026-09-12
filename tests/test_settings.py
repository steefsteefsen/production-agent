"""Rechte-Allowlist: .claude/settings.json erlaubt die Werkzeuge des Orchestrators, nie aber git push."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETTINGS = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
PERM = SETTINGS["permissions"]


def push_allowed(perm: dict) -> bool:
    """Falsifikationshilfe: erlaubt die Allowlist git push?"""
    return any("git push" in a for a in perm.get("allow", []))


def test_git_push_denied_never_allowed():
    assert "Bash(git push:*)" in PERM["deny"]
    assert push_allowed(PERM) is False


def test_required_tools_allowed():
    joined = " ".join(PERM["allow"])
    for needed in ("pytest", "python", "ruff", "bandit", "git add", "git commit", "make", "npm"):
        assert needed in joined, needed


def test_git_push_in_allow_is_red_falsification():
    assert push_allowed({"allow": ["Bash(git push:*)"], "deny": []}) is True


def test_secrets_and_decisions_stay_denied():
    for d in ("Read(.env)", "Edit(.env)", "Edit(decisions.yaml)"):
        assert d in PERM["deny"]
