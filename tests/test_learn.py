"""Rechte-Lernen: verweigerte Befehle werden zu Allow-Vorschlägen – aber nie git push/rm -rf/.env/…"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "autopilot"))
import cc  # noqa: E402
import orchestrate  # noqa: E402


def _denials(*cmds: str) -> str:
    return json.dumps(
        {"permission_denials": [{"tool_name": "Bash", "tool_input": {"command": c}} for c in cmds]}
    )


def test_pattern_is_tool_plus_subcommand():
    assert cc._pattern("npm test --watch") == "Bash(npm test:*)"
    assert cc._pattern("pytest -q") == "Bash(pytest:*)"


def test_learn_writes_new_patterns(tmp_path):
    p = tmp_path / "denied.json"
    new = cc.learn_denials(_denials("npm test --watch"), p)
    assert new == ["Bash(npm test:*)"]
    again = cc.learn_denials(_denials("npm test --watch"), p)  # kein Duplikat
    assert again == []


def test_denied_git_push_never_learned_falsification(tmp_path):
    denied = tmp_path / "denied.json"
    local = tmp_path / "settings.local.json"
    cc.learn_denials(_denials("git push origin main", "npm test"), denied)
    added = orchestrate.apply_learned(denied, local)
    assert not any("git push" in a for a in added)
    assert "Bash(npm test:*)" in added
    assert "git push" not in local.read_text(encoding="utf-8")


def test_apply_learned_skips_deny_and_secrets(tmp_path):
    denied = tmp_path / "denied.json"
    local = tmp_path / "settings.local.json"
    cc.learn_denials(_denials("rm -rf /tmp/x", "cat .env", "python autopilot/x.py"), denied)
    added = orchestrate.apply_learned(denied, local)
    assert all("rm -rf" not in a and ".env" not in a for a in added)
    assert added == ["Bash(python autopilot/x.py:*)"] or "Bash(python autopilot:*)" in added
