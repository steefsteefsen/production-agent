"""Coverage-Lücken schließen: messages.py, pipeline_view.py, mes_router.py.

Verifikation: jede öffentliche Funktion und jedes Modell wird aufgerufen.
Falsifikation: fehlerhafte Eingaben lösen die erwarteten Fehler aus.
"""

from __future__ import annotations

import importlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# messages.py – severity_to_priority + Pydantic-Modelle
# ---------------------------------------------------------------------------


def test_severity_to_priority_alle_baender():
    from production_agent.data.messages import severity_to_priority

    assert severity_to_priority(1000) == 1  # >=800 → Prio 1
    assert severity_to_priority(800) == 1
    assert severity_to_priority(799) == 2  # 600-799 → Prio 2
    assert severity_to_priority(600) == 2
    assert severity_to_priority(599) == 3  # 400-599 → Prio 3
    assert severity_to_priority(400) == 3
    assert severity_to_priority(399) == 4  # <400 → Prio 4
    assert severity_to_priority(1) == 4


def test_alarm_event_valide():
    from production_agent.data.messages import AlarmEvent

    ev = AlarmEvent(
        source_node="L1-S1/Wickler",
        alarm_id="E-4711/2026-01-01T10:00:00",
        alarm_code="E-4711",
        severity=850,
        priority=1,
        message="Folienriss",
        active=True,
        ts=datetime(2026, 1, 1, 10, 0, 0, tzinfo=UTC),
        topic="plant/L1/Wickler/alarm",
    )
    assert ev.alarm_code == "E-4711"
    assert ev.priority == 1


def test_alarm_event_falsches_topic_typ():
    from production_agent.data.messages import AlarmEvent
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AlarmEvent(
            source_node="L1-S1",
            alarm_id="id",
            alarm_code="E-1",
            severity=100,
            priority=4,
            message="x",
            active=True,
            ts=datetime(2026, 1, 1, tzinfo=UTC),
            topic="plant/L1/S1/state",  # 'state' statt 'alarm'
        )


def test_alarm_event_falsches_topic_schema_falsification():
    from production_agent.data.messages import AlarmEvent
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        AlarmEvent(
            source_node="L1-S1",
            alarm_id="id",
            alarm_code="E-1",
            severity=100,
            priority=4,
            message="x",
            active=True,
            ts=datetime(2026, 1, 1, tzinfo=UTC),
            topic="wrong/format",  # falsche Struktur
        )


def test_state_change_valide():
    from production_agent.data.messages import StateChange

    sc = StateChange(
        source_node="L1-S1",
        equipment_id="L1-S1",
        line_id="L1",
        station="S1",
        old_state="Execute",
        new_state="Held",
        ts=datetime(2026, 1, 1, 10, 5, 0, tzinfo=UTC),
        topic="plant/L1/S1/state",
    )
    assert sc.new_state == "Held"


def test_state_change_falsches_topic_falsification():
    from production_agent.data.messages import StateChange
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        StateChange(
            source_node="L1-S1",
            equipment_id="L1-S1",
            line_id="L1",
            station="S1",
            old_state="Execute",
            new_state="Held",
            ts=datetime(2026, 1, 1, tzinfo=UTC),
            topic="plant/L1/S1/alarm",  # 'alarm' statt 'state'
        )


def test_order_progress_valide():
    from production_agent.data.messages import OrderProgress

    op = OrderProgress(
        source_node="L1/MES",
        order_id="A-001",
        line_id="L1",
        product="Film",
        planned_qty=1000,
        produced_qty=500,
        due_ts=datetime(2026, 1, 2, tzinfo=UTC),
        order_priority=2,
        ts=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        topic="plant/L1/MES/order",
    )
    assert op.order_id == "A-001"
    assert op.order_priority == 2


def test_order_progress_falsches_topic_falsification():
    from production_agent.data.messages import OrderProgress
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        OrderProgress(
            source_node="L1/MES",
            order_id="A-001",
            line_id="L1",
            product="Film",
            planned_qty=1000,
            produced_qty=500,
            due_ts=datetime(2026, 1, 2, tzinfo=UTC),
            order_priority=2,
            ts=datetime(2026, 1, 1, tzinfo=UTC),
            topic="plant/L1/MES/alarm",  # 'alarm' statt 'order'
        )


# ---------------------------------------------------------------------------
# pipeline_view.py – get_lineage
# ---------------------------------------------------------------------------


def test_get_lineage_bekanntes_ereignis(small_db):
    from production_agent.data.pipeline_view import get_lineage

    conn = sqlite3.connect(small_db)
    row = conn.execute("SELECT event_id FROM downtime_events_gold LIMIT 1").fetchone()
    conn.close()
    assert row is not None, "small_db enthält keine Gold-Ereignisse"
    result = get_lineage(row[0], str(small_db))
    assert result is not None
    assert "event_id" in result
    assert "rules_applied" in result
    assert isinstance(result["rules_applied"], list)
    assert len(result["rules_applied"]) > 0


def test_get_lineage_unbekanntes_ereignis_falsification(small_db):
    from production_agent.data.pipeline_view import get_lineage

    result = get_lineage(999999, str(small_db))
    assert result is None, "Nicht-existierendes Ereignis muss None liefern"


def test_get_lineage_regeln_enthalten_sequenzierung(small_db):
    from production_agent.data.pipeline_view import get_lineage

    conn = sqlite3.connect(small_db)
    row = conn.execute("SELECT event_id FROM downtime_events_gold LIMIT 1").fetchone()
    conn.close()
    result = get_lineage(row[0], str(small_db))
    assert result is not None
    sequ_rules = [r for r in result["rules_applied"] if "Sequenzierung" in r]
    assert sequ_rules, "Sequenzierungsregel fehlt in rules_applied"


# ---------------------------------------------------------------------------
# mes_router.py – FastAPI-Routen
# ---------------------------------------------------------------------------


@pytest.fixture
def mes_client(replay_env):
    from fastapi import FastAPI

    from production_agent.api import mes_router

    importlib.reload(mes_router)
    test_app = FastAPI()
    test_app.include_router(mes_router.router)
    return TestClient(test_app)


def test_mes_events_liefert_liste(mes_client):
    r = mes_client.get("/mes/events", params={"line_id": "L1"})
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_mes_events_limit_falsification(mes_client):
    """Falsifikation: limit=0 ist ungültig."""
    r = mes_client.get("/mes/events", params={"line_id": "L1", "limit": 0})
    assert r.status_code == 422  # Pydantic-Validierung


def test_mes_lineage_bekanntes_ereignis(mes_client, small_db):
    conn = sqlite3.connect(small_db)
    row = conn.execute("SELECT event_id FROM downtime_events_gold LIMIT 1").fetchone()
    conn.close()
    assert row is not None
    r = mes_client.get(f"/mes/lineage/{row[0]}")
    assert r.status_code == 200
    data = r.json()
    assert "event_id" in data
    assert "rules_applied" in data


def test_mes_lineage_unbekanntes_ereignis_falsification(mes_client):
    r = mes_client.get("/mes/lineage/999999")
    assert r.status_code == 404


def test_mes_line_bekannte_linie(mes_client):
    r = mes_client.get("/mes/line/L1")
    assert r.status_code == 200
    data = r.json()
    assert "line" in data
    assert "equipment" in data
    assert "orders" in data


def test_mes_line_unbekannte_linie_falsification(mes_client):
    r = mes_client.get("/mes/line/NICHTVORHANDEN-XYZ")
    assert r.status_code == 404


def test_mes_stream_startet(mes_client):
    """Verifikation: /mes/stream antwortet mit text/event-stream."""
    with mes_client.stream("GET", "/mes/stream", params={"line_id": "L1", "speed": 1_000_000}) as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")
