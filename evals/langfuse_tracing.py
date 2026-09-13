"""Langfuse-Tracing für den Graph – nur aktiv, wenn Settings.langfuse_enabled.

Bewusst als optionaler Callback, der beim Graph-Aufruf über `config={"callbacks": [...]}`
injiziert wird – so bleibt der Graph-Code (src/production_agent/graph/workflow.py) unberührt und
funktioniert ohne Langfuse ohne Netzverbindung und ohne Abhängigkeit.

Bei aktiviertem Langfuse wird jeder LangGraph-Knoten zu einem Span, jeder Werkzeug-/LLM-Aufruf zu
einem Child-Span (langchain-Integration von Langfuse). PROMPT_VERSION reist als Trace-Metadatum mit.

Bewusst minimal: Tracing ist Observability (was lief, wie lange, welche Version), NICHT
Drift-Monitoring, NICHT Retraining (ADR-0007).
"""

from __future__ import annotations

import os
from typing import Any

from production_agent.config import get_settings
from production_agent.graph.prompts import PROMPT_VERSION


def tracing_config(base: dict[str, Any] | None = None) -> dict[str, Any]:
    """LangGraph-/LangChain-Config mit Langfuse-Callback anreichern, falls aktiviert.

    Gibt die (ggf. um `callbacks` und `metadata` erweiterte) Config zurück. Ist Langfuse nicht
    konfiguriert (kein Public/Secret-Key), bleibt die Config unverändert – kein Import-Fehler,
    keine Netzverbindung.
    """
    cfg: dict[str, Any] = dict(base or {})
    handler = build_callback()
    if handler is None:
        return cfg
    callbacks = list(cfg.get("callbacks", []))
    callbacks.append(handler)
    cfg["callbacks"] = callbacks
    metadata = dict(cfg.get("metadata", {}))
    metadata.setdefault("prompt_version", PROMPT_VERSION)
    metadata.setdefault("langfuse_tags", ["production-agent", f"prompt:{PROMPT_VERSION}"])
    cfg["metadata"] = metadata
    return cfg


def build_callback():
    """Langfuse-CallbackHandler bauen, wenn aktiviert; sonst None.

    Setzt die von Langfuse erwarteten Umgebungsvariablen aus den Settings (Keys, Host), damit der
    Client sich ohne globale .env-Konfiguration initialisiert. Schlägt der Import oder die
    Initialisierung fehl (z. B. Langfuse nicht installiert), wird None zurückgegeben – der Lauf
    darf daran nicht scheitern.
    """
    settings = get_settings()
    if not settings.langfuse_enabled:
        return None
    try:
        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
        os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
        os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)
        from langfuse.langchain import CallbackHandler

        return CallbackHandler()
    except Exception:  # noqa: BLE001 – Tracing ist optional, nie den Lauf abbrechen
        return None
