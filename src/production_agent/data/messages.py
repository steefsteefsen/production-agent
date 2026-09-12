"""MES-Nachrichtenformat: OPC UA A&C + ISA-95 JSON-Events (ADR-0010).

Topic-Schema: plant/<line>/<station>/<alarm|state|order>
Priorität 1–4 aus OPC-UA-Severity-Bändern (≥800 → 1, 600–799 → 2, 400–599 → 3, <400 → 4).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


def severity_to_priority(severity: int) -> int:
    """OPC-UA-Severity-Band → ISA-18.2-Priorität (1 = höchste … 4 = niedrigste)."""
    if severity >= 800:
        return 1
    if severity >= 600:
        return 2
    if severity >= 400:
        return 3
    return 4


def _validate_topic(v: str, expected_type: str) -> str:
    parts = v.split("/")
    if len(parts) != 4 or parts[0] != "plant":
        raise ValueError("Topic muss plant/<line>/<station>/<typ> sein")
    if parts[3] not in ("alarm", "state", "order"):
        raise ValueError("Topic-Typ muss alarm, state oder order sein")
    if parts[3] != expected_type:
        raise ValueError(f"Topic-Typ muss '{expected_type}' sein")
    return v


class AlarmEvent(BaseModel):
    """OPC UA Alarms and Conditions – ISA-18.2-konformer MES-Alarm (ADR-0010)."""

    source_node: str  # OPC UA NodeId der Quelle (z. B. "L1-S1/Folienwickler")
    alarm_id: str  # Eindeutige Alarm-Instanz-ID
    alarm_code: str  # Herstellercode (z. B. "E-4711")
    severity: int = Field(ge=1, le=1000)  # OPC-UA-Severity 1..1000
    priority: int = Field(ge=1, le=4)  # ISA-18.2: 1 = höchste … 4 = niedrigste
    message: str  # Klartextbeschreibung
    active: bool = True  # True = aktiv, False = quittiert/gelöscht
    ts: datetime  # Ereigniszeitpunkt (ISO 8601, UTC)
    topic: str  # plant/<line>/<station>/alarm

    @field_validator("topic")
    @classmethod
    def _topic_alarm(cls, v: str) -> str:
        return _validate_topic(v, "alarm")


class StateChange(BaseModel):
    """PackML-Zustandswechsel eines Betriebsmittels (ISA-TR88.00.02)."""

    source_node: str  # OPC UA NodeId des Betriebsmittels
    equipment_id: str  # z. B. "L1-S1"
    line_id: str
    station: str
    old_state: str  # PackML-Zustand vorher
    new_state: str  # PackML-Zustand nachher (Stopped | Held | Suspended | Aborted | Execute)
    ts: datetime
    topic: str  # plant/<line>/<station>/state

    @field_validator("topic")
    @classmethod
    def _topic_state(cls, v: str) -> str:
        return _validate_topic(v, "state")


class OrderProgress(BaseModel):
    """ISA-95-Auftragsfortschritt (WorkRequest / JobOrder, IEC 62264)."""

    source_node: str  # OPC UA NodeId der MES-Schnittstelle
    order_id: str
    line_id: str
    product: str
    planned_qty: int = Field(ge=0)
    produced_qty: int = Field(ge=0)
    due_ts: datetime
    order_priority: int = Field(ge=1, le=4)  # 1 = dringendster Auftrag
    ts: datetime  # Stand der Meldung
    topic: str  # plant/<line>/<station>/order

    @field_validator("topic")
    @classmethod
    def _topic_order(cls, v: str) -> str:
        return _validate_topic(v, "order")
