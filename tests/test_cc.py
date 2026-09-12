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


def test_is_quota_only_on_real_error():
    assert cc.is_quota(1, '{"is_error": true, "api_error_status": "429"}') is True
    assert cc.is_quota(1, '{"is_error": true, "error": "usage limit, resets at 14:00"}') is True


def test_is_quota_not_on_successful_reviewer_answer_falsification():
    # Erfolgreiche Reviewer-Antwort mit dem Wort "limit" im Text löst KEINE Pause aus
    ok = '{"is_error": false, "result": "Alles ok, kein rate limit Problem", "verdict": "pass"}'
    assert cc.is_quota(0, ok) is False
    assert cc.is_quota(0, "alles in Ordnung") is False


def test_preflight_without_abo_login_does_not_start_falsification(tmp_path, monkeypatch):
    fake = tmp_path / "claude"
    fake.write_text("#!/usr/bin/env bash\necho 'Auth: API key (ANTHROPIC_API_KEY)'\nexit 0\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")
    ok, msg = cc.preflight()
    assert ok is False and "Abo" in msg
