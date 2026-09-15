"""MCP-Server 1: MES – reine Live-Simulation der Linie (drei fachlich geschnittene Werkzeuge).

Nur der aktuelle Anlagenzustand: Linienstatus, aktive Alarme, offener Produktionsplan. Historische
Vorfallsuche liegt im knowledge-Server, die Wirkungsschätzung im business_rules-Server (fachliche
Trennung). Bewusst KEIN generisches SQL-Werkzeug: jedes Werkzeug läuft durch sql_guard (Read-only,
Allowlist, Zeilenlimit), wird auditiert und liefert kompakte, injection-sichere Ergebnisse.

Start: python -m production_agent.mcp.mes_server   (stdio-Transport)
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

from fastmcp import FastMCP

from production_agent.config import get_settings
from production_agent.security.audit import AuditLog
from production_agent.security.injection_guard import sanitize_tool_result
from production_agent.security.sql_guard import open_readonly, run_readonly

settings = get_settings()
audit = AuditLog(settings.audit_log_path)
mcp = FastMCP("mes")

_MAX_ACTIVE_ALARMS = 100


def _now() -> str:
    """Replay-Uhr: Historie ist alles VOR now, Gegenwart ist das Fenster BIS now (kein Leck).

    Reihenfolge: SIM_NOW aus der Umgebung (setzt build_graph für die MCP-Server) vor dem – beim
    Import eingefrorenen – settings.sim_now; sonst die echte Zeit. Ohne den Umgebungsvorrang sähe
    der Live-Betrieb die Replay-Uhr nicht und leckte das laufende Ereignis (ADR-0002)."""
    return (
        os.environ.get("SIM_NOW")
        or settings.sim_now
        or datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    )


def _query(sql: str, params: tuple[Any, ...] = (), tool: str = "", limit: int | None = None) -> str:
    conn = open_readonly(settings.mes_db_path)
    max_rows = limit if limit is not None else settings.max_rows_per_tool
    try:
        rows = run_readonly(conn, sql, params, max_rows=max_rows)
    finally:
        conn.close()
    audit.record("tool_call", tool=tool, sql=sql, params=params, rows=len(rows))
    return _envelope(rows, tool)


def _envelope(rows: list[dict[str, Any]], tool: str) -> str:
    """Kürzt auf Zeilenebene – das Ergebnis bleibt gültiges JSON (Bug aus Falsifikationstest)."""
    limit = settings.max_tool_result_chars
    payload = json.dumps(rows, ensure_ascii=False, default=str)
    while len(payload) > limit and len(rows) > 1:
        rows = rows[: max(1, len(rows) // 2)]
        rows = [*rows, {"_truncated": True, "_kept_rows": len(rows)}]
        payload = json.dumps(rows, ensure_ascii=False, default=str)
        rows = rows[:-1]
    return sanitize_tool_result(payload, max_chars=limit * 2, source=f"mes.{tool}")


@mcp.tool()
def get_line_status(line_id: str) -> str:
    """Aktueller PackML-Zustand aller Betriebsmittel einer Linie sowie laufender Auftrag.

    Nutze dies, wenn du dir als Erstes ein Bild vom Zustand der Linie machen willst –
    Pflicht-Einstieg jeder Analyse.
    """
    sql = """
        SELECT e.equipment_id, e.name, e.position, s.packml_state, s.ts
        FROM equipment e
        JOIN equipment_state s ON s.equipment_id = e.equipment_id
        WHERE e.line_id = ?
          AND s.ts = (SELECT MAX(ts) FROM equipment_state
                      WHERE equipment_id = e.equipment_id AND ts <= ?)
        ORDER BY e.position
    """
    return _query(sql, (line_id, _now()), tool="get_line_status")


@mcp.tool()
def get_active_alarms(line_id: str, minutes: int = 30) -> str:
    """Aktive Alarme der letzten N Minuten auf der Linie, sortiert nach Zeit (ISA-18.2-Priorität).

    Nutze dies, wenn du wissen willst, welche Alarme die Störung ausgelöst haben und
    ob eine Alarmflut vorliegt.
    """
    sql = """
        SELECT a.ts, a.equipment_id, a.alarm_code, a.priority, a.sequence_id
        FROM alarms_silver a JOIN equipment e ON e.equipment_id = a.equipment_id
        WHERE e.line_id = ? AND a.ts >= datetime(?, ?) AND a.ts <= ?
        ORDER BY a.ts DESC
    """
    now = _now()
    return _query(
        sql,
        (line_id, now, f"-{int(minutes)} minutes", now),
        tool="get_active_alarms",
        limit=_MAX_ACTIVE_ALARMS,
    )


@mcp.tool()
def get_production_plan(line_id: str) -> str:
    """Offene Aufträge der Linie mit Soll/Ist-Menge, Termin und Priorität.

    Nutze dies, wenn du wissen willst, welche Aufträge noch laufen und welche Termine
    durch den Stillstand gefährdet sein könnten.
    """
    sql = """
        SELECT order_id, product, planned_qty, produced_qty, due_ts, priority
        FROM production_orders WHERE line_id = ? AND produced_qty < planned_qty
        ORDER BY priority, due_ts
    """
    return _query(sql, (line_id,), tool="get_production_plan")


if __name__ == "__main__":
    mcp.run()
