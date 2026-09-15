"""Zustand des Production-Agent-Graphen (eine Untersuchung = ein Thread)."""

from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, Field


class Hypothesis(BaseModel):
    """Strukturierte Ausgabe von Knoten 4 (Ursacheneingrenzung)."""

    cause: str
    reason_code: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    expected_downtime_min: float = Field(ge=0.0)


class AgentState(TypedDict, total=False):
    line_id: str
    line_status: dict[str, Any]  # Schritt 1
    production_plan: list[dict[str, Any]]  # Schritt 1
    alarms: list[dict[str, Any]]  # Schritt 2
    alarm_flood: bool  # ISA-18.2 ≥10/10min
    knowledge: list[dict[str, Any]]  # Schritt 3 (RAG + ähnliche Vorfälle)
    hypothesis: dict[str, Any]  # Schritt 4 (Hypothesis als dict, serialisierbar)
    impact: dict[str, Any]  # Schritt 5
    actions: list[dict[str, Any]]  # Schritt 6 (nach action_policy)
    applied_threshold: float  # Schritt 6: tatsächlich angewandte Konfidenzschwelle (runtime.yaml)
    judge_results: list[dict[str, Any]]  # Schritt 6b (Beleg-Prüfung je Maßnahme)
    approval: dict[str, Any] | None  # Schritt 7 (Freigabeentscheidung)
    trace: list[str]  # menschenlesbares Protokoll je Knoten
    errors: list[str]
