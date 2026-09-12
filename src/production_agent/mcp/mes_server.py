"""MCP-Server 1: MES – sechs fachlich geschnittene Werkzeuge.

Bewusst KEIN generisches SQL-Werkzeug. Jedes Werkzeug spricht die Sprache des
Produktionsleiters, läuft durch sql_guard (Read-only, Allowlist, Zeilenlimit),
wird auditiert und liefert kompakte, injection-sichere Ergebnisse.

Start: python -m production_agent.mcp.mes_server   (stdio-Transport)
"""

from __future__ import annotations

import json
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
_MAX_ALARM_HISTORY = 20
_MAX_SIMILAR_INCIDENTS = 5


def _now() -> str:
    """Replay-Uhr: Historie ist alles VOR now, Gegenwart ist das Fenster BIS now (kein Leck)."""
    return settings.sim_now or datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


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
def get_alarm_history(alarm_code: str, limit: int = 20) -> str:
    """Historische Störungsereignisse (Gold) mit diesem Erstalarmcode – Dauer, Ursache, Maßnahme.

    Nutze dies, wenn du verstehen willst, wie oft und wie lange dieser Alarm in der
    Vergangenheit zur Störung geführt hat (max. 20 Einträge).
    """
    sql = """
        SELECT event_id, start_ts, duration_min, packml_state, reason_code,
               alarm_count, alarm_flood, resolution_action
        FROM downtime_events_gold WHERE first_alarm_code = ? AND end_ts <= ?
        ORDER BY start_ts DESC LIMIT ?
    """
    return _query(
        sql,
        (alarm_code, _now(), min(int(limit), _MAX_ALARM_HISTORY)),
        tool="get_alarm_history",
        limit=_MAX_ALARM_HISTORY,
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


@mcp.tool()
def estimate_impact(line_id: str, expected_downtime_min: float) -> str:
    """Schätzt Produktionsverlust, Kosten (EUR) und Termingefährdung je Auftrag. Regelbasiert.

    Nutze dies, wenn du dem Produktionsleiter zeigen willst, was der Stillstand kostet
    und welche Aufträge ihren Termin reißen.
    """
    conn = open_readonly(settings.mes_db_path)
    try:
        line = run_readonly(conn, "SELECT * FROM lines WHERE line_id = ?", (line_id,), 1)
        orders = run_readonly(
            conn,
            "SELECT order_id, planned_qty, produced_qty, due_ts FROM production_orders "
            "WHERE line_id = ? AND produced_qty < planned_qty ORDER BY due_ts",
            (line_id,),
            settings.max_rows_per_tool,
        )
    finally:
        conn.close()
    if not line:
        return sanitize_tool_result('{"error": "line not found"}', source="mes.estimate_impact")
    rate = line[0]["design_rate_per_hour"]
    cost_rate = line[0]["cost_per_downtime_minute_eur"]
    lost_units = round(rate * expected_downtime_min / 60)

    now_dt = datetime.fromisoformat(_now().replace(" ", "T"))
    orders_detail = []
    for o in orders:
        remaining = o["planned_qty"] - o["produced_qty"]
        production_time_min = remaining / rate * 60
        try:
            due_dt = datetime.fromisoformat(o["due_ts"].replace(" ", "T"))
            time_until_due_min = (due_dt - now_dt).total_seconds() / 60
        except (ValueError, AttributeError):
            time_until_due_min = float("inf")
        # Puffer = Zeit bis Termin − Restproduktionszeit − erwarteter Stillstand
        buffer_min = time_until_due_min - production_time_min - expected_downtime_min
        orders_detail.append(
            {
                "order_id": o["order_id"],
                "buffer_min": round(buffer_min, 1),
                "at_risk": buffer_min < 0,
            }
        )

    result = {
        "expected_downtime_min": expected_downtime_min,
        "lost_units": lost_units,
        "cost_eur": round(cost_rate * expected_downtime_min, 2),
        "orders": orders_detail,
        "orders_at_risk": [o["order_id"] for o in orders_detail if o["at_risk"]],
        "method": (
            "regelbasiert: Nennleistung × Dauer; Kostensatz je Minute aus Stammdaten; "
            "Puffer = Zeit bis Termin − Restproduktionszeit − Stillstand"
        ),
    }
    audit.record(
        "tool_call", tool="estimate_impact", line_id=line_id, minutes=expected_downtime_min
    )
    return sanitize_tool_result(
        json.dumps(result, ensure_ascii=False), source="mes.estimate_impact"
    )


@mcp.tool()
def find_similar_incidents(alarm_codes: list[str], packml_state: str, limit: int = 5) -> str:
    """Case-Based Reasoning: ähnliche frühere Störungen nach Alarmcodes und PackML-Zustand.

    Nutze dies, wenn du Belege aus der Vergangenheit suchst, die deine Hypothese zur
    Ursache stützen oder widerlegen (max. 5 Einträge).
    """
    placeholders = ",".join("?" for _ in alarm_codes) or "''"
    sql = f"""
        SELECT g.event_id, g.start_ts, g.duration_min, g.first_alarm_code, g.reason_code,
               g.resolution_action, i.root_cause, i.action_taken, i.outcome, i.doc_ref
        FROM downtime_events_gold g LEFT JOIN incident_history i ON i.event_id = g.event_id
        WHERE g.first_alarm_code IN ({placeholders}) AND g.packml_state = ? AND g.end_ts <= ?
        ORDER BY g.start_ts DESC LIMIT ?
    """  # noqa: S608  # nosec B608 – nur "?"-Platzhalter, Werte laufen als Parameter
    params = (*alarm_codes, packml_state, _now(), min(int(limit), _MAX_SIMILAR_INCIDENTS))
    return _query(sql, params, tool="find_similar_incidents", limit=_MAX_SIMILAR_INCIDENTS)


if __name__ == "__main__":
    mcp.run()
