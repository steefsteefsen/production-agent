"""MES-Endpunkte (nur lesend, Guard-geschützt, auditiert). ADR-0010.

GET /mes/stream        – SSE: Alarme des Demo-Ereignisses, zeitgetreu (speed-Parameter)
GET /mes/events        – Gold-Ereignisse einer Linie
GET /mes/lineage/{id}  – Bronze → Silber → Gold Herkunftskette
GET /mes/line/{id}     – Aktueller Linienstatus
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from production_agent.config import get_settings
from production_agent.data.pipeline_view import get_lineage
from production_agent.data.replay import case_for_event_id, latest_replay_ts
from production_agent.data.simulator import CATALOG, generate, load_decisions
from production_agent.security.audit import AuditLog
from production_agent.security.sql_guard import open_readonly, run_readonly

# PackML-Zustände, die eine gestörte Station kennzeichnen (Gegenstück zu "Execute")
_FAULT_STATES = {"Held", "Aborted", "Stopped", "Suspended"}

router = APIRouter(prefix="/mes", tags=["MES"])

_DECISIONS_PATH = Path(__file__).resolve().parents[3] / "decisions.yaml"


def _audit() -> AuditLog:
    return AuditLog(get_settings().audit_log_path)


@router.get("/stream")
async def mes_stream(
    line_id: str = "L1",
    speed: float = Query(default=60.0, ge=0.1, le=1_000_000, description="Zeitrafferrate"),
) -> StreamingResponse:
    """SSE: Alarme des Demo-Ereignisses zeitgetreu (speed = Sim-Sekunden je Echtzeit-Sekunde)."""

    async def _gen() -> Any:
        dec = load_decisions(_DECISIONS_PATH)
        evs = generate(dec)
        demo = evs[-1 - dec["simulation"]["demo_ereignis_index_von_hinten"]]
        stationen = dec["linie"]["stationen"]
        if not demo.alarms:
            return
        station_name = (
            stationen[demo.station] if demo.station < len(stationen) else f"S{demo.station}"
        )
        ref_ts = demo.alarms[0][0]
        for ts, code, prio, sev in demo.alarms:
            delay = max(0.0, (ts - ref_ts).total_seconds() / speed)
            if delay > 0:
                await asyncio.sleep(delay)
            ref_ts = ts
            payload = {
                "source_node": f"{line_id}-S{demo.station}/{station_name}",
                "alarm_id": f"{code}/{ts.isoformat()}",
                "alarm_code": code,
                "severity": sev,
                "priority": prio,
                "message": CATALOG[demo.reason]["cause"],
                "active": True,
                "ts": ts.isoformat(),
                "topic": f"plant/{line_id}/{station_name}/alarm",
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    _audit().record("mes_stream_gestartet", line_id=line_id)
    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/events")
def mes_events(
    line_id: str = "L1",
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Gold-Ereignisse einer Linie, neueste zuerst."""
    settings = get_settings()
    conn = open_readonly(settings.mes_db_path)
    try:
        rows = run_readonly(
            conn,
            "SELECT event_id, start_ts, end_ts, duration_min, packml_state, reason_code, "
            "first_alarm_code, first_alarm_prio, alarm_count, alarm_flood, cost_eur "
            "FROM downtime_events_gold WHERE line_id = ? ORDER BY start_ts DESC",
            (line_id,),
            max_rows=limit,
        )
    finally:
        conn.close()
    _audit().record("mes_events_abgerufen", line_id=line_id, n=len(rows))
    return rows


@router.get("/lineage/{event_id}")
def mes_lineage(event_id: int) -> dict[str, Any]:
    """Bronze → Silber → Gold Herkunftskette für ein Ereignis."""
    settings = get_settings()
    result = get_lineage(event_id, settings.mes_db_path)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Ereignis {event_id} nicht gefunden")
    _audit().record("mes_lineage_abgerufen", event_id=event_id)
    return result


@router.get("/line/{line_id}")
def mes_line(line_id: str, event_id: int | None = Query(default=None)) -> dict[str, Any]:
    """Linienstatus ZUR REPLAY-ZEIT des gewählten Ereignisses (Konsistenz mit Störungsstrom).

    Die PackML-Zustände werden auf `s.ts <= SIM_NOW` gefiltert – genau wie das MES-Werkzeug
    get_line_status. Ohne diesen Filter lieferte der Endpunkt den GLOBAL jüngsten Zustand (alle
    Stationen nach dem Wiederanlauf wieder „Execute"), im Widerspruch zur laufenden Störung
    (Fehler aus Live-Test). Ohne `event_id` gilt die Uhr des jüngsten Ereignisses (Demo-Default).
    Eine zur Replay-Zeit gestörte Station trägt zusätzlich die Verknüpfung zum aktiven Ereignis.
    """
    settings = get_settings()
    conn = open_readonly(settings.mes_db_path)
    try:
        line_rows = run_readonly(
            conn,
            "SELECT line_id, name, plant, design_rate_per_hour, cost_per_downtime_minute_eur "
            "FROM lines WHERE line_id = ?",
            (line_id,),
            max_rows=1,
        )
        if not line_rows:
            raise HTTPException(status_code=404, detail=f"Linie {line_id} nicht gefunden")
        # Replay-Uhr bestimmen: konkretes Ereignis, sonst jüngstes (Demo-Default).
        sim_now: str | None = None
        if event_id is not None:
            case = case_for_event_id(conn, event_id)
            sim_now = case.now if case else None
        if sim_now is None:
            sim_now = latest_replay_ts(conn)
        # PackML-Zustand ZUR Replay-Zeit (<= sim_now); ohne Replay-Uhr der bisherige Global-Stand.
        if sim_now is not None:
            equip_rows = run_readonly(
                conn,
                "SELECT e.equipment_id, e.name, e.position, s.packml_state, s.ts "
                "FROM equipment e "
                "LEFT JOIN equipment_state s "
                "  ON e.equipment_id = s.equipment_id "
                "  AND s.ts = ("
                "    SELECT MAX(ts) FROM equipment_state "
                "    WHERE equipment_id = e.equipment_id AND ts <= ?"
                "  ) "
                "WHERE e.line_id = ? ORDER BY e.position",
                (sim_now, line_id),
                max_rows=20,
            )
        else:
            equip_rows = run_readonly(
                conn,
                "SELECT e.equipment_id, e.name, e.position, s.packml_state, s.ts "
                "FROM equipment e "
                "LEFT JOIN equipment_state s "
                "  ON e.equipment_id = s.equipment_id "
                "  AND s.ts = ("
                "    SELECT MAX(ts) FROM equipment_state WHERE equipment_id = e.equipment_id"
                "  ) "
                "WHERE e.line_id = ? ORDER BY e.position",
                (line_id,),
                max_rows=20,
            )
        order_rows = run_readonly(
            conn,
            "SELECT order_id, product, planned_qty, produced_qty, due_ts, priority "
            "FROM production_orders WHERE line_id = ? ORDER BY priority",
            (line_id,),
            max_rows=10,
        )
        # Zur Replay-Zeit aktives Störungsereignis (start <= now <= end) – für die Held-Verknüpfung.
        active = None
        if sim_now is not None:
            active_rows = run_readonly(
                conn,
                "SELECT event_id, reason_code, first_alarm_code, alarm_count, start_ts, end_ts "
                "FROM downtime_events_gold "
                "WHERE line_id = ? AND start_ts <= ? AND (end_ts IS NULL OR end_ts >= ?) "
                "ORDER BY start_ts DESC",
                (line_id, sim_now, sim_now),
                max_rows=5,
            )
            active = active_rows[0] if active_rows else None
    finally:
        conn.close()
    # Gestörte Station(en) mit dem aktiven Ereignis verknüpfen (Alarm-ID sichtbar/klickbar).
    equipment = []
    for row in equip_rows:
        d = dict(row)
        if active is not None and d.get("packml_state") in _FAULT_STATES:
            d["alarm"] = {
                "event_id": active["event_id"],
                "first_alarm_code": active["first_alarm_code"],
                "reason_code": active["reason_code"],
                "alarm_count": active["alarm_count"],
            }
        equipment.append(d)
    _audit().record("mes_line_abgerufen", line_id=line_id, sim_now=sim_now)
    return {
        "line": line_rows[0],
        "equipment": equipment,
        "orders": order_rows,
        "sim_now": sim_now,
        "active_event": active,
    }
