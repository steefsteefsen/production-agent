"""Guardian S7: Geheimnisse getrennt von Konfiguration. Prüffunktionen sind importierbar."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "autopilot"))

import guardian  # noqa: E402

ENV = "ANTHROPIC_API_KEY=sk-secret-0123456789abcdef\nLANGFUSE_PUBLIC_KEY=pk-lf-abcdefgh12345678\n"


def test_secret_value_in_doc_is_error():
    files = {"docs/x.md": "hier steht sk-secret-0123456789abcdef versehentlich"}
    assert any("S7" in e for e in guardian.check_env_leak(ENV, files))


def test_config_key_in_env_is_s7b_error():
    env = "MES_DB_PATH=data/gold/mes.sqlite\nANTHROPIC_API_KEY=sk-x-0123456789abcdef\n"
    errs = guardian.check_env_keys(env)
    assert any("MES_DB_PATH" in e and "S7b" in e for e in errs)


def test_model_name_from_settings_not_flagged_falsification():
    # Modellname steht in settings.env (Konfiguration), nicht in .env → S7 kennt ihn nicht
    files = {"README.md": "Modell: claude-sonnet-5, Fast: claude-haiku-4-5-20251001"}
    assert guardian.check_env_leak(ENV, files) == []


def test_example_placeholder_ok_falsification():
    example = "ANTHROPIC_API_KEY=sk-ant-EXAMPLE\nLANGFUSE_PUBLIC_KEY=pk-lf-EXAMPLE\n"
    assert guardian.check_example_suffix(example) == []
    assert guardian.check_example_suffix("ANTHROPIC_API_KEY=real-value-here\n")
