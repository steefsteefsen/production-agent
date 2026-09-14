"""Robuste Verarbeitung strukturierter LLM-Ausgaben (with_structured_output).

Bekanntes Muster bei Tool-Calls mit Listen-/Objektfeldern: das echte Modell liefert die
strukturierte Ausgabe manchmal als JSON-String statt als natives Objekt – z. B. landet der ganze
Payload als `actions='{"actions":[...]}'` im ersten Feld. Ohne Absicherung wirft die
Pydantic-Validierung dann einen ValidationError (tritt nur mit LLM_MODE=live auf).

Strategie: die Live-Chains laufen mit `include_raw=True`, damit `invoke()` NICHT crasht, sondern den
Rohtext mitliefert; schlägt die Standard-Validierung fehl, wird der Tool-Call-Args einmal per
json.loads geparst und – falls das gesamte Objekt doppelt kodiert wurde – entschachtelt. Wirklich
kaputtes JSON schlägt weiterhin SAUBER fehl (klarer Fehler mit Rohtext); NIE still eine leere Liste.
"""

from __future__ import annotations

import json
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def coerce_structured(value: Any, model_cls: type[T]) -> T:
    """Formt strukturierte Ausgaben ins Zielmodell; robust gegen JSON-String-Kodierung."""
    if isinstance(value, model_cls):
        return value
    data: Any = value
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Strukturausgabe ist kein gültiges JSON: {value[:160]!r}") from e
    fields = set(model_cls.model_fields)
    if isinstance(data, dict):
        # Ein Feld enthält den gesamten JSON als String → entschachteln
        for k, v in list(data.items()):
            if isinstance(v, str) and v.strip()[:1] in "{[":
                try:
                    inner = json.loads(v)
                except json.JSONDecodeError:
                    continue
                if isinstance(inner, dict) and fields & set(inner):
                    data = inner  # ganzes Objekt war doppelt kodiert
                    break
                data[k] = inner  # nur dieses Feld war ein JSON-String
    elif isinstance(data, list) and len(fields) == 1:
        data = {next(iter(fields)): data}  # nackte Liste → einziges Listenfeld
    return model_cls.model_validate(data)  # ungültige Struktur → ValidationError (sauberer Fehler)


def invoke_structured(chain: Any, messages: Any, model_cls: type[T]) -> T:
    """Ruft eine strukturierte Chain auf und liefert immer das Zielmodell – oder scheitert klar."""
    result = chain.invoke(messages)
    if isinstance(result, model_cls):
        return result  # Standard-/Mockfall: schon das Zielobjekt
    if isinstance(result, dict) and ("parsed" in result or "raw" in result):
        # include_raw=True: {"raw": AIMessage, "parsed": obj|None, "parsing_error": err|None}
        if result.get("parsed") is not None:
            return result["parsed"]
        raw = result.get("raw")
        tool_calls = getattr(raw, "tool_calls", None) or []
        content: Any = tool_calls[0].get("args") if tool_calls else getattr(raw, "content", None)
        if content is None:
            raise ValueError(
                "Strukturierte Ausgabe nicht verwertbar "
                f"(parsing_error={result.get('parsing_error')})"
            )
        return coerce_structured(content, model_cls)
    return coerce_structured(result, model_cls)
