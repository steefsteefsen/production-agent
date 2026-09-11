"""Zustand des Production-Agent-Graphen (eine Untersuchung = ein Thread)."""

from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    line_id: str
    line_status: dict[str, Any]  # Schritt 1
    alarms: list[dict[str, Any]]  # Schritt 2
    alarm_flood: bool  # ISA-18.2 ≥10/10min
    knowledge: list[dict[str, Any]]  # Schritt 3 (RAG + ähnliche Vorfälle)
    hypotheses: list[dict[str, Any]]  # Schritt 4 (Ursache, Konfidenz)
    impact: dict[str, Any]  # Schritt 5
    actions: list[dict[str, Any]]  # Schritt 6 (nach action_policy)
    approval: dict[str, Any] | None  # Schritt 7 (Freigabeentscheidung)
    trace: list[str]  # menschenlesbares Protokoll je Knoten
    errors: list[str]
