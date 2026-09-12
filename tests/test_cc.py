"""Abo-Betrieb (cc.py): claude-Subprozesse ohne API-Key, Modelle aus settings.env, Quota-Erkennung, Abo-Preflight."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "autopilot"))

import cc  # noqa: E402


def test_env_strips_api_key_falsification(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-secret-0123456789")
    assert "ANTHROPIC_API_KEY" not in cc.env()  # Abo-Betrieb: kein Key im Subprozess
    assert cc.env(api_billing=True).get("ANTHROPIC_API_KEY") == "sk-secret-0123456789"


def test_models_from_settings():
    assert cc.model("builder") == "sonnet"
    assert cc.model("reviewer") == "sonnet"
    assert cc.model("decider") == "opus"


def test_is_quota_detects_429_falsification():
    assert cc.is_quota(1, "Error: 429 too many requests") is True
    assert cc.is_quota(1, "usage limit reached, resets at 14:00") is True
    assert cc.is_quota(0, "alles in Ordnung") is False


def test_preflight_without_abo_login_does_not_start_falsification(tmp_path, monkeypatch):
    fake = tmp_path / "claude"
    fake.write_text("#!/usr/bin/env bash\necho 'Auth: API key (ANTHROPIC_API_KEY)'\nexit 0\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    ok, msg = cc.preflight()
    assert ok is False and "Abo" in msg
