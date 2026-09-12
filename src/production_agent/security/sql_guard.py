"""Read-only-SQL-Guard für den MES-MCP-Server.

Prinzip: Der Agent bekommt nie freies SQL. Die 6 fachlichen Werkzeuge bauen ihre
Abfragen selbst und laufen durch diesen Guard, damit ein Fehler in einem Werkzeug
nie zu Schreibzugriffen führen kann (Defense in Depth).
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Sequence
from typing import Any

ALLOWED_TABLES: frozenset[str] = frozenset(
    {
        "lines",
        "equipment",
        "equipment_state",
        "alarms_silver",
        "downtime_events_gold",
        "production_orders",
        "downtime_reason_codes",
        "incident_history",
        "ai4i_snapshots",
        "short_stops",
    }
)

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|"
    r"reindex|truncate|grant|revoke)\b",
    re.IGNORECASE,
)
_TABLE_REF = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.IGNORECASE)


class SqlGuardError(ValueError):
    """Abfrage verletzt die Sicherheitsregeln."""


def validate_query(sql: str) -> str:
    stripped = sql.strip().rstrip(";")
    if ";" in stripped:
        raise SqlGuardError("Mehrere Statements sind nicht erlaubt.")
    if not re.match(r"^\s*(select|with)\b", stripped, re.IGNORECASE):
        raise SqlGuardError("Nur SELECT/WITH-Abfragen sind erlaubt.")
    if _FORBIDDEN.search(stripped):
        raise SqlGuardError("Schreibende oder administrative Schlüsselwörter sind verboten.")
    for table in _TABLE_REF.findall(stripped):
        if table.lower() not in ALLOWED_TABLES:
            raise SqlGuardError(f"Tabelle '{table}' steht nicht auf der Allowlist.")
    return stripped


def open_readonly(db_path: str) -> sqlite3.Connection:
    """Öffnet SQLite im Read-only-Modus (URI mode=ro) – zweite Schutzschicht."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def run_readonly(
    conn: sqlite3.Connection,
    sql: str,
    params: Sequence[Any] = (),
    max_rows: int = 200,
) -> list[dict[str, Any]]:
    """Führt eine validierte Abfrage aus und begrenzt die Zeilenzahl hart."""
    safe_sql = validate_query(sql)
    cur = conn.execute(safe_sql, tuple(params))
    rows = cur.fetchmany(max_rows + 1)
    truncated = len(rows) > max_rows
    result = [dict(r) for r in rows[:max_rows]]
    if truncated:
        result.append({"_truncated": True, "_max_rows": max_rows})
    return result
