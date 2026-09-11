"""LangGraph-Workflow: 7 Knoten, Freigabe über interrupt(), SQLite-Checkpointer.

Skelett mit vollständiger Sicherheits- und Ablaufstruktur. Die LLM-Aufrufe in Knoten
4 und 6 werden in WP3 ergänzt; alle Knoten sind heute schon einzeln testbar.
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from production_agent.config import get_settings
from production_agent.graph.state import AgentState
from production_agent.security.action_policy import RecommendedAction, apply_policy
from production_agent.security.audit import AuditLog

settings = get_settings()
audit = AuditLog(settings.audit_log_path)


def _log(state: AgentState, msg: str) -> list[str]:
    return [*state.get("trace", []), msg]


# --- Knoten (Tools werden in WP3 über langchain-mcp-adapters injiziert) -----------------


def capture_status(state: AgentState) -> dict[str, Any]:
    return {"trace": _log(state, "1 Zustand erfasst (get_line_status)")}


def analyze_alarms(state: AgentState) -> dict[str, Any]:
    alarms = state.get("alarms", [])
    flood = len(alarms) >= 10  # ISA-18.2: ≥10 Alarme in 10 min → Alarmflut
    return {"alarm_flood": flood, "trace": _log(state, f"2 Alarme analysiert, Flut={flood}")}


def retrieve_knowledge(state: AgentState) -> dict[str, Any]:
    return {"trace": _log(state, "3 Wissen abgerufen (RAG + find_similar_incidents)")}


def narrow_cause(state: AgentState) -> dict[str, Any]:
    return {"trace": _log(state, "4 Ursache eingegrenzt (LLM + Regeln)")}


def estimate_impact(state: AgentState) -> dict[str, Any]:
    return {"trace": _log(state, "5 Wirkung geschätzt (estimate_impact)")}


def derive_actions(state: AgentState) -> dict[str, Any]:
    raw = [RecommendedAction(**a) for a in state.get("actions", [])]
    safe = apply_policy(raw, settings.confidence_threshold_recommend)
    return {
        "actions": [a.model_dump() for a in safe],
        "trace": _log(state, f"6 Maßnahmen abgeleitet, {len(safe)} nach Policy"),
    }


def approval_gate(state: AgentState) -> Command:
    """Schritt 7: Der Graph hält an. Der Mensch entscheidet. Empfehlen ≠ Ausführen."""
    decision = interrupt(
        {
            "question": "Maßnahmen freigeben?",
            "actions": state.get("actions", []),
            "impact": state.get("impact", {}),
        }
    )
    audit.record("approval", decision=decision, line_id=state.get("line_id"))
    return Command(
        goto=END, update={"approval": decision, "trace": _log(state, "7 Freigabe erfasst")}
    )


def route_after_alarms(state: AgentState) -> str:
    """Verzweigung: Bei Alarmflut zuerst Wissen abrufen; sonst direkt Ursache eingrenzen."""
    return "retrieve_knowledge" if state.get("alarm_flood") else "narrow_cause"


def build_graph(checkpoint_path: str | None = None):
    g = StateGraph(AgentState)
    g.add_node("capture_status", capture_status)
    g.add_node("analyze_alarms", analyze_alarms)
    g.add_node("retrieve_knowledge", retrieve_knowledge)
    g.add_node("narrow_cause", narrow_cause)
    g.add_node("estimate_impact", estimate_impact)
    g.add_node("derive_actions", derive_actions)
    g.add_node("approval_gate", approval_gate)

    g.set_entry_point("capture_status")
    g.add_edge("capture_status", "analyze_alarms")
    g.add_conditional_edges("analyze_alarms", route_after_alarms)
    g.add_edge("retrieve_knowledge", "narrow_cause")
    g.add_edge("narrow_cause", "estimate_impact")
    g.add_edge("estimate_impact", "derive_actions")
    g.add_edge("derive_actions", "approval_gate")

    if checkpoint_path is None:
        from langgraph.checkpoint.memory import InMemorySaver

        return g.compile(checkpointer=InMemorySaver())
    import sqlite3

    conn = sqlite3.connect(checkpoint_path, check_same_thread=False)
    return g.compile(checkpointer=SqliteSaver(conn))
