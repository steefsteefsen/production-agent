"""MCP-Server 3: business_rules – deterministische Geschäftsregeln, kein Modell beteiligt.

Ein Werkzeug: estimate_impact schätzt Produktionsverlust, Kosten (EUR) und Termingefährdung je
Auftrag rein regelbasiert (Nennleistung × Dauer, Kostensatz aus Stammdaten, Pufferrechnung). Bewusst
getrennt von Live-Simulation (mes) und Wissenssuche (knowledge): hier entscheidet Arithmetik,
nicht das Sprachmodell. Read-only über sql_guard, auditiert, injection-sicher.

Start: python -m production_agent.mcp.business_rules_server   (stdio-Transport)
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime

from fastmcp import FastMCP

from production_agent.config import get_settings
from production_agent.security.audit import AuditLog
from production_agent.security.injection_guard import sanitize_tool_result
from production_agent.security.sql_guard import open_readonly, run_readonly

settings = get_settings()
audit = AuditLog(settings.audit_log_path)
mcp = FastMCP("business_rules")


def _now() -> str:
    """Replay-Uhr: SIM_NOW-Vorrang, dann settings.sim_now, sonst echte Zeit (ADR-0002)."""
    return (
        os.environ.get("SIM_NOW")
        or settings.sim_now
        or datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    )


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
        return sanitize_tool_result(
            '{"error": "line not found"}', source="business_rules.estimate_impact"
        )
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
        json.dumps(result, ensure_ascii=False), source="business_rules.estimate_impact"
    )


if __name__ == "__main__":
    mcp.run()
