"""Unit-Tests für data/messages.py – Schema, Severity-Bänder, Topic-Validierung."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from production_agent.data.messages import (
    AlarmEvent,
    OrderProgress,
    StateChange,
    severity_to_priority,
)

TS = datetime(2026, 9, 11, 6, 0, 0)

# ---------------------------------------------------------------------------
# severity_to_priority
# ---------------------------------------------------------------------------


def test_band_1_ab_800():
    assert severity_to_priority(800) == 1
    assert severity_to_priority(1000) == 1


def test_band_2_600_bis_799():
    assert severity_to_priority(600) == 2
    assert severity_to_priority(799) == 2


def test_band_3_400_bis_599():
    assert severity_to_priority(400) == 3
    assert severity_to_priority(599) == 3


def test_band_4_unter_400():
    assert severity_to_priority(1) == 4
    assert severity_to_priority(399) == 4


# ---------------------------------------------------------------------------
# AlarmEvent
# ---------------------------------------------------------------------------


def _alarm(**kwargs) -> AlarmEvent:
    defaults = dict(
        source_node="L1-S1/Folienwickler",
        alarm_id="E-4711/T",
        alarm_code="E-4711",
        severity=720,
        priority=2,
        message="Folienriss",
        ts=TS,
        topic="plant/L1/Folienwickler/alarm",
    )
    defaults.update(kwargs)
    return AlarmEvent(**defaults)


def test_alarm_event_vollstaendig():
    ev = _alarm()
    assert ev.alarm_code == "E-4711"
    assert ev.priority == 2
    assert ev.active is True


def test_alarm_event_source_node_pflicht():
    """Falsifikation: ohne source_node → ValidationError."""
    with pytest.raises(ValidationError):
        AlarmEvent(
            alarm_id="x",
            alarm_code="E-4711",
            severity=720,
            priority=2,
            message="Test",
            ts=TS,
            topic="plant/L1/Folienwickler/alarm",
        )


def test_alarm_event_severity_minimum():
    with pytest.raises(ValidationError):
        _alarm(severity=0)  # < 1


def test_alarm_event_severity_maximum():
    with pytest.raises(ValidationError):
        _alarm(severity=1001)  # > 1000


def test_alarm_event_priority_minimum():
    with pytest.raises(ValidationError):
        _alarm(priority=0)  # < 1


def test_alarm_event_priority_maximum():
    with pytest.raises(ValidationError):
        _alarm(priority=5)  # > 4


def test_alarm_event_topic_schema_korrekt():
    ev = _alarm(topic="plant/L1/Folienwickler/alarm")
    parts = ev.topic.split("/")
    assert parts[0] == "plant" and len(parts) == 4 and parts[3] == "alarm"


def test_alarm_event_topic_falscher_typ():
    """Falsifikation: state als Topic-Typ für AlarmEvent → ValidationError."""
    with pytest.raises(ValidationError):
        _alarm(topic="plant/L1/Folienwickler/state")


def test_alarm_event_topic_falsches_format():
    with pytest.raises(ValidationError):
        _alarm(topic="L1/Folienwickler/alarm")  # fehlendes plant-Präfix


def test_alarm_event_topic_zu_viele_teile():
    with pytest.raises(ValidationError):
        _alarm(topic="plant/L1/Folienwickler/alarm/extra")


# ---------------------------------------------------------------------------
# StateChange
# ---------------------------------------------------------------------------


def test_state_change_vollstaendig():
    sc = StateChange(
        source_node="L1-S1",
        equipment_id="L1-S1",
        line_id="L1",
        station="Folienwickler",
        old_state="Execute",
        new_state="Held",
        ts=TS,
        topic="plant/L1/Folienwickler/state",
    )
    assert sc.new_state == "Held"
    assert sc.topic.endswith("/state")


def test_state_change_source_node_pflicht():
    with pytest.raises(ValidationError):
        StateChange(
            equipment_id="L1-S1",
            line_id="L1",
            station="Folienwickler",
            old_state="Execute",
            new_state="Held",
            ts=TS,
            topic="plant/L1/Folienwickler/state",
        )


def test_state_change_topic_falscher_typ():
    with pytest.raises(ValidationError):
        StateChange(
            source_node="L1-S1",
            equipment_id="L1-S1",
            line_id="L1",
            station="Folienwickler",
            old_state="Execute",
            new_state="Held",
            ts=TS,
            topic="plant/L1/Folienwickler/alarm",  # alarm statt state
        )


# ---------------------------------------------------------------------------
# OrderProgress
# ---------------------------------------------------------------------------


def test_order_progress_vollstaendig():
    op = OrderProgress(
        source_node="L1-MES",
        order_id="A-2207",
        line_id="L1",
        product="Karton 12er",
        planned_qty=4800,
        produced_qty=3120,
        due_ts=datetime(2026, 9, 11, 10, 0, 0),
        order_priority=1,
        ts=TS,
        topic="plant/L1/Palettierer/order",
    )
    assert op.order_id == "A-2207"
    assert op.order_priority == 1


def test_order_progress_source_node_pflicht():
    with pytest.raises(ValidationError):
        OrderProgress(
            order_id="A-2207",
            line_id="L1",
            product="Karton 12er",
            planned_qty=4800,
            produced_qty=3120,
            due_ts=datetime(2026, 9, 11, 10, 0, 0),
            order_priority=1,
            ts=TS,
            topic="plant/L1/Palettierer/order",
        )


def test_order_progress_topic_falscher_typ():
    with pytest.raises(ValidationError):
        OrderProgress(
            source_node="L1-MES",
            order_id="A-2207",
            line_id="L1",
            product="Karton 12er",
            planned_qty=4800,
            produced_qty=3120,
            due_ts=datetime(2026, 9, 11, 10, 0, 0),
            order_priority=1,
            ts=TS,
            topic="plant/L1/Palettierer/state",  # state statt order
        )


def test_order_progress_menge_negativ():
    with pytest.raises(ValidationError):
        OrderProgress(
            source_node="L1-MES",
            order_id="A-2207",
            line_id="L1",
            product="Karton 12er",
            planned_qty=-1,  # negativ → Fehler
            produced_qty=0,
            due_ts=datetime(2026, 9, 11, 10, 0, 0),
            order_priority=1,
            ts=TS,
            topic="plant/L1/Palettierer/order",
        )


# ---------------------------------------------------------------------------
# FastAPI: 422 bei fehlendem source_node
# ---------------------------------------------------------------------------


def test_alarm_event_ohne_source_node_422():
    """POST-Body ohne source_node → 422 Unprocessable Entity."""
    from fastapi import APIRouter, FastAPI
    from fastapi.testclient import TestClient

    _router = APIRouter()

    @_router.post("/alarm")
    def _create(ev: AlarmEvent) -> dict:
        return ev.model_dump(mode="json")

    _app = FastAPI()
    _app.include_router(_router)
    client = TestClient(_app, raise_server_exceptions=False)

    r = client.post(
        "/alarm",
        json={
            "alarm_id": "E-4711/T",
            "alarm_code": "E-4711",
            "severity": 720,
            "priority": 2,
            "message": "Test",
            "ts": "2026-09-11T06:00:00",
            "topic": "plant/L1/Folienwickler/alarm",
            # source_node fehlt absichtlich
        },
    )
    assert r.status_code == 422
