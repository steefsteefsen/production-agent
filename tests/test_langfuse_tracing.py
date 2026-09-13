"""Tests für den optionalen Langfuse-Callback (evals/langfuse_tracing.py).

Kernzusage: ohne gesetzte Keys passiert nichts (keine Netzverbindung, kein Callback). Mit Keys
reist PROMPT_VERSION als Metadatum mit. Alles ohne echte Langfuse-Verbindung.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVALS = ROOT / "evals"
if str(EVALS) not in sys.path:
    sys.path.insert(0, str(EVALS))


def _load():
    spec = importlib.util.spec_from_file_location("langfuse_tracing", EVALS / "langfuse_tracing.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


lt = _load()


def test_tracing_config_ohne_keys_unveraendert_verifikation(monkeypatch):
    """Verifikation: ohne Langfuse-Keys bleibt die Config unverändert – kein Callback, kein Netz."""
    from production_agent.config import get_settings

    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    get_settings.cache_clear()

    base = {"configurable": {"thread_id": "x"}}
    cfg = lt.tracing_config(base)
    assert "callbacks" not in cfg
    assert cfg["configurable"]["thread_id"] == "x"
    assert lt.build_callback() is None
    get_settings.cache_clear()


def test_tracing_config_mit_keys_setzt_metadatum_falsification(monkeypatch):
    """Falsifikation: sind Keys gesetzt (langfuse_enabled), MUSS die Config die Prompt-Version als
    Metadatum tragen – fehlte sie, ginge die Versionsinformation im Trace verloren.

    Der CallbackHandler wird gestubt, damit kein echter Langfuse-Client/Netz nötig ist.
    """
    from production_agent.config import get_settings

    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    get_settings.cache_clear()

    monkeypatch.setattr(lt, "build_callback", lambda: object())

    cfg = lt.tracing_config({"configurable": {"thread_id": "y"}})
    assert "callbacks" in cfg and len(cfg["callbacks"]) == 1
    from production_agent.graph.prompts import PROMPT_VERSION

    assert cfg["metadata"]["prompt_version"] == PROMPT_VERSION
    get_settings.cache_clear()
