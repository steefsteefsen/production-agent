"""Prozesslokale Live-Sicht auf den jüngsten Untersuchungslauf (kein neuer Server/Port).

Der API-Prozess sammelt während des SSE-Laufs die tatsächlichen Werkzeugaufrufe (MCP) und
Guard-Entscheidungen (sql_guard, injection_guard, Judge) aus dem echten Graph-State. Die UI-Tabs
(MCP, Sicherheit) lesen diese Live-Sicht über die API. Das ersetzt NICHT das persistente AuditLog –
es ist die schlanke, für die Oberfläche aufbereitete Momentaufnahme des laufenden Falls.
"""

from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import Any

_LOCK = Lock()
_STATE: dict[str, list[dict[str, Any]]] = {"tools": [], "security": []}


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def reset() -> None:
    """Zu Beginn eines neuen Laufs die Live-Sicht leeren."""
    with _LOCK:
        _STATE["tools"] = []
        _STATE["security"] = []


def record_tool_call(server: str, tool: str, params: dict, raw: dict) -> None:
    """Einen echten Werkzeugaufruf festhalten (Server, Werkzeug, Parameter, rohe Antwort)."""
    with _LOCK:
        _STATE["tools"].append(
            {"ts": _ts(), "server": server, "tool": tool, "params": params, "raw": raw}
        )


def record_security(guard: str, allowed: bool, detail: str) -> None:
    """Eine echte Guard-Entscheidung festhalten (sql_guard/injection_guard/judge)."""
    with _LOCK:
        _STATE["security"].append(
            {"ts": _ts(), "guard": guard, "allowed": bool(allowed), "detail": detail}
        )


def snapshot() -> dict[str, list[dict[str, Any]]]:
    """Aktuelle Live-Sicht (Kopie) für die API."""
    with _LOCK:
        return {"tools": list(_STATE["tools"]), "security": list(_STATE["security"])}
