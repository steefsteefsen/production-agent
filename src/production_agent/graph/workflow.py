"""LangGraph-Workflow: 7 Knoten, Freigabe über interrupt(), SQLite-Checkpointer.

Knotenreihenfolge (decisions.yaml „einfachster Graph: keine Verzweigung"):
  1 capture_status → 2 analyze_alarms → 3 retrieve_knowledge
  → 4 narrow_cause (LLM) → 5 estimate_impact → 6 derive_actions (LLM) → 7 approval_gate

Werkzeuge werden über build_graph(tools=...) injiziert:
  dict[str, Callable[..., str]]  (Schlüssel = MCP-Werkzeugname)
Für Tests: Python-Funktionen mit identischer Signatur.
Für echten Protokollbetrieb: via fastmcp.Client über stdio (build_tools_from_mcp, opt-in).
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel

from production_agent.graph.judge import JudgeVerdict, cited_evidence, judge_action
from production_agent.graph.prompts import SYSTEM_DERIVE_ACTIONS, SYSTEM_NARROW_CAUSE
from production_agent.graph.state import AgentState, Hypothesis
from production_agent.graph.structured import invoke_structured
from production_agent.security.action_policy import RecommendedAction, apply_policy
from production_agent.security.audit import AuditLog

_Tools = dict[str, Callable[..., str]]


def _get_settings():
    from production_agent.config import get_settings

    return get_settings()


def _log(state: AgentState, msg: str) -> list[str]:
    return [*state.get("trace", []), msg]


_TOOL_DATA_RE = re.compile(r"<tool_data\b[^>]*>(.*?)</tool_data>", re.S)
_WARN_RE = re.compile(r"^\s*\[WARNUNG:[^\]]*\]\s*", re.S)
_TRUNC_RE = re.compile(r"\s*\[\.\.\. gekürzt \.\.\.\]\s*$")


def _parse(raw: Any) -> Any:
    """JSON aus MCP-Werkzeugergebnis parsen. Echte Werkzeuge kapseln das Ergebnis in eine
    <tool_data>-Hülle (injection_guard); Hülle, [WARNUNG:…]-Zeile und [... gekürzt ...]-Hinweis
    werden zuerst entfernt, dann JSON. Bei Fehler leere Liste. (Fixture-Werkzeuge liefern rohes
    JSON – das lief, verdeckte aber den Integrationsfehler.)"""
    if isinstance(raw, (list, dict)):
        return raw
    if not isinstance(raw, str):
        return []
    body = raw
    m = _TOOL_DATA_RE.search(raw)
    if m:
        body = m.group(1)
    body = _WARN_RE.sub("", body.strip())
    body = _TRUNC_RE.sub("", body).strip()
    try:
        return json.loads(body)
    except (ValueError, TypeError):
        return []


def _first_alarm_code(alarms: list[dict]) -> str:
    """Erstalarm = der zeitlich früheste Alarm (kleinster ts). get_active_alarms sortiert DESC nach
    ts, der Erstalarm ist also das letzte Element und fiele sonst aus den häufigsten Codes heraus.
    (sequence_id ist die gemeinsame Ereignis-ID der Serie, nicht die Reihenfolge – daher ts.)"""
    cand = [a for a in alarms if isinstance(a, dict) and a.get("alarm_code")]
    if not cand:
        return ""
    return str(min(cand, key=lambda a: str(a.get("ts", "")))["alarm_code"])


def _top_alarm_codes(alarms: list[dict], n: int = 3) -> list[str]:
    """Häufigste alarm_code-Werte aus der Alarmliste – der Erstalarm ist immer enthalten und
    führt die Liste an (sonst sähe die Wissensabfrage den auslösenden Alarm nicht)."""
    counts: dict[str, int] = {}
    for a in alarms:
        code = str(a.get("alarm_code", ""))
        if code:
            counts[code] = counts.get(code, 0) + 1
    ranked = [c for c, _ in sorted(counts.items(), key=lambda x: -x[1])]
    first = _first_alarm_code(alarms)
    ordered = ([first] if first else []) + [c for c in ranked if c != first]
    return ordered[:n]


_PACKML_STOPPED = ("Held", "Suspended", "Stopped", "Aborted")


def _extract_packml_state(line_status: dict | list) -> str:
    """PackML-Zustand der STEHENDEN Station. Akzeptiert {"rows": [...]}, eine Liste von Equipment-
    Zuständen oder ein einzelnes Equipment-Dict; bevorzugt einen Stopp-Zustand (Held/Suspended/
    Stopped/Aborted), da die Störung genau dort steht, nicht am ersten Equipment der Liste."""
    rows: Any = None
    if isinstance(line_status, dict):
        if "rows" in line_status:
            rows = line_status.get("rows")
        elif "packml_state" in line_status:
            return str(line_status.get("packml_state", "Unknown"))
    elif isinstance(line_status, list):
        rows = line_status
    if isinstance(rows, list) and rows:
        for r in rows:
            if isinstance(r, dict) and str(r.get("packml_state", "")) in _PACKML_STOPPED:
                return str(r["packml_state"])
        first = rows[0]
        if isinstance(first, dict):
            return str(first.get("packml_state", "Unknown"))
    return "Unknown"


def _flood_in_window(alarms: list[dict], window_min: int = 10, threshold: int = 10) -> bool:
    """ISA-18.2: ≥threshold Alarme innerhalb window_min Minuten."""
    sim_now = os.environ.get("SIM_NOW") or _get_settings().sim_now
    if sim_now:
        try:
            now_dt = datetime.fromisoformat(sim_now.replace(" ", "T"))
            if now_dt.tzinfo is None:
                now_dt = now_dt.replace(tzinfo=UTC)
        except ValueError:
            now_dt = datetime.now(UTC)
    else:
        now_dt = datetime.now(UTC)

    count = 0
    for a in alarms:
        ts_raw = a.get("ts", "")
        if not ts_raw:
            continue
        try:
            ts = datetime.fromisoformat(str(ts_raw).replace(" ", "T"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            if (now_dt - ts).total_seconds() <= window_min * 60:
                count += 1
        except ValueError:
            continue
    return count >= threshold


# ---------------------------------------------------------------------------
# Knoten 1 – Linienstatus und Produktionsplan erfassen
# ---------------------------------------------------------------------------


def _make_capture_status(tools: _Tools):
    def capture_status(state: AgentState) -> dict[str, Any]:
        line_id = state.get("line_id", "L1")
        raw_status = tools["get_line_status"](line_id=line_id)
        raw_plan = tools["get_production_plan"](line_id=line_id)
        line_status = _parse(raw_status)
        production_plan = _parse(raw_plan)
        return {
            "line_status": line_status if isinstance(line_status, dict) else {"rows": line_status},
            "production_plan": production_plan if isinstance(production_plan, list) else [],
            "trace": _log(state, "1 Linienstatus und Produktionsplan erfasst"),
        }

    return capture_status


# ---------------------------------------------------------------------------
# Knoten 2 – Alarme analysieren (30-min-Fenster, Alarmflut ISA-18.2)
# ---------------------------------------------------------------------------


def _make_analyze_alarms(tools: _Tools):
    def analyze_alarms(state: AgentState) -> dict[str, Any]:
        line_id = state.get("line_id", "L1")
        raw = tools["get_active_alarms"](line_id=line_id, minutes=30)
        alarms = _parse(raw)
        if not isinstance(alarms, list):
            alarms = []
        flood = _flood_in_window(alarms, window_min=10, threshold=10)
        return {
            "alarms": alarms,
            "alarm_flood": flood,
            "trace": _log(state, f"2 Alarme analysiert ({len(alarms)}), Alarmflut={flood}"),
        }

    return analyze_alarms


# ---------------------------------------------------------------------------
# Knoten 3 – Wissen abrufen (RAG + ähnliche Vorfälle)
# ---------------------------------------------------------------------------


def _make_retrieve_knowledge(tools: _Tools):
    def retrieve_knowledge(state: AgentState) -> dict[str, Any]:
        alarms = state.get("alarms", [])
        codes = _top_alarm_codes(alarms, n=3)
        query = " ".join(codes) if codes else "Störung Verpackungslinie"

        raw_docs = tools["search_maintenance_docs"](query=query, top_k=5)
        docs = _parse(raw_docs)

        packml = _extract_packml_state(state.get("line_status", {}))
        raw_incidents = tools["find_similar_incidents"](
            alarm_codes=codes or [""], packml_state=packml, limit=5
        )
        incidents = _parse(raw_incidents)

        knowledge = (docs if isinstance(docs, list) else []) + (
            incidents if isinstance(incidents, list) else []
        )
        return {
            "knowledge": knowledge,
            "trace": _log(
                state,
                f"3 Wissen abgerufen: {len(docs if isinstance(docs, list) else [])} Dokumente, "
                f"{len(incidents if isinstance(incidents, list) else [])} ähnliche Vorfälle",
            ),
        }

    return retrieve_knowledge


# ---------------------------------------------------------------------------
# Knoten 4 – Ursache eingrenzen (LLM, strukturierte Ausgabe: Hypothesis)
# ---------------------------------------------------------------------------


def _make_narrow_cause(llm_chain):
    def narrow_cause(state: AgentState) -> dict[str, Any]:
        context = json.dumps(
            {
                "line_status": state.get("line_status", {}),
                "alarms": state.get("alarms", [])[:20],
                "alarm_flood": state.get("alarm_flood", False),
                "knowledge": state.get("knowledge", [])[:10],
            },
            ensure_ascii=False,
            default=str,
        )
        messages = [
            SystemMessage(content=SYSTEM_NARROW_CAUSE),
            HumanMessage(content=f"Kontext:\n{context}"),
        ]
        hypo: Hypothesis = invoke_structured(llm_chain, messages, Hypothesis)
        return {
            "hypothesis": hypo.model_dump(),
            "trace": _log(
                state,
                f"4 Hypothese: {hypo.reason_code} (Konfidenz {hypo.confidence:.2f}, "
                f"Stillstand ~{hypo.expected_downtime_min} min)",
            ),
        }

    return narrow_cause


# ---------------------------------------------------------------------------
# Knoten 5 – Wirkung schätzen (regelbasiert, MES-Werkzeug)
# ---------------------------------------------------------------------------


def _make_estimate_impact(tools: _Tools):
    def estimate_impact(state: AgentState) -> dict[str, Any]:
        line_id = state.get("line_id", "L1")
        hypo = state.get("hypothesis", {})
        expected_dt = float(hypo.get("expected_downtime_min", 30.0))
        raw = tools["estimate_impact"](line_id=line_id, expected_downtime_min=expected_dt)
        impact = _parse(raw)
        return {
            "impact": impact if isinstance(impact, dict) else {"raw": raw},
            "trace": _log(state, f"5 Wirkung geschätzt: {expected_dt} min Stillstand"),
        }

    return estimate_impact


# ---------------------------------------------------------------------------
# Knoten 6 – Maßnahmen ableiten (LLM, strukturierte Ausgabe: RecommendedActions)
# ---------------------------------------------------------------------------


class _ActionsOutput(BaseModel):
    """Strukturierte LLM-Ausgabe von Knoten 6: Liste empfohlener Maßnahmen."""

    actions: list[RecommendedAction]


def _incident_ids_from_knowledge(knowledge: list) -> set[str]:
    """Vorfall-IDs (event_id) aus den abgerufenen ähnlichen Vorfällen. Diese stammen aus
    downtime_events_gold (find_similar_incidents) und existieren dort per Konstruktion – nur sie
    dürfen in einer rationale als Beleg zitiert werden (Stefan-Nachbedingung Knoten 6)."""
    ids: set[str] = set()
    for k in knowledge or []:
        if isinstance(k, dict) and k.get("event_id") not in (None, ""):
            ids.add(str(k["event_id"]))
    return ids


def _rationale_cites_incident(rationale: str, valid_ids: set[str]) -> bool:
    """True, wenn die rationale mindestens eine gültige Vorfall-ID nennt (Teilstring, tolerant für
    Formen wie 'EVT-001' oder ganze Zahlen)."""
    return any(vid and vid in (rationale or "") for vid in valid_ids)


def _make_derive_actions(llm_chain):
    def derive_actions(state: AgentState) -> dict[str, Any]:
        settings = _get_settings()
        knowledge = state.get("knowledge", [])
        # Vorfälle (mit event_id) VOR Dokumenten in den Kontext – sonst füllt [:5] nur Dokumente und
        # das LLM sieht keine Vorfall-ID, die es laut Nachbedingung zitieren muss.
        incidents = [
            k for k in knowledge if isinstance(k, dict) and k.get("event_id") not in (None, "")
        ]
        docs = [
            k
            for k in knowledge
            if not (isinstance(k, dict) and k.get("event_id") not in (None, ""))
        ]
        context = json.dumps(
            {
                "hypothesis": state.get("hypothesis", {}),
                "impact": state.get("impact", {}),
                "knowledge": (incidents + docs)[:5],
            },
            ensure_ascii=False,
            default=str,
        )
        messages = [
            SystemMessage(content=SYSTEM_DERIVE_ACTIONS),
            HumanMessage(content=f"Kontext:\n{context}"),
        ]
        out: _ActionsOutput = invoke_structured(llm_chain, messages, _ActionsOutput)
        # im Cockpit gespeicherte Schwelle wird genutzt (runtime.yaml-Override, frisch gelesen)
        from production_agent.config import runtime_value

        threshold = runtime_value(
            "konfidenz.schwelle_empfehlung", settings.confidence_threshold_recommend
        )
        safe = apply_policy(out.actions, threshold)
        # Nachbedingung (Stefan): jede Maßnahme muss mindestens eine Vorfall-ID aus
        # downtime_events_gold nennen. Sind ähnliche Vorfälle abrufbar, werden Maßnahmen
        # ohne gültigen Beleg verworfen.
        valid_ids = _incident_ids_from_knowledge(knowledge)
        if valid_ids:
            grounded = [a for a in safe if _rationale_cites_incident(a.rationale, valid_ids)]
        else:
            grounded = safe  # keine ähnlichen Vorfälle abrufbar → keine Vorfall-ID erzwingbar
        dropped = len(safe) - len(grounded)
        return {
            "actions": [a.model_dump() for a in grounded],
            "applied_threshold": float(threshold),
            "trace": _log(
                state,
                f"6 Maßnahmen abgeleitet, {len(grounded)} mit Vorfall-ID belegt"
                + (f" ({dropped} ohne Beleg verworfen)" if dropped else "")
                + f" (Konfidenzschwelle {float(threshold):.2f} aus runtime.yaml)",
            ),
        }

    return derive_actions


# ---------------------------------------------------------------------------
# Knoten 6b – Beleg-Prüfung (LLM-as-Judge, eigenes Modell, getrennter Kontext)
# ---------------------------------------------------------------------------


def _make_check_evidence(judge_chain):
    def check_evidence(state: AgentState, config=None) -> dict[str, Any]:
        knowledge = state.get("knowledge", [])
        actions = state.get("actions", [])
        # geführte Demo: entfernt den Beleg der ersten Maßnahme (manipulierter/fehlender Beleg),
        # damit der Judge sichtbar NICHT bestätigt. Default aus; Produktivpfad unberührt.
        tamper = bool((config or {}).get("configurable", {}).get("demo_tamper", False))
        results: list[dict[str, Any]] = []
        for i, action in enumerate(actions):
            evidence = cited_evidence(action, knowledge)
            if tamper and i == 0:
                evidence = []
            results.append(judge_action(judge_chain, action, evidence))
        confirmed = sum(1 for r in results if r["verified"])
        return {
            "judge_results": results,
            "trace": _log(
                state,
                f"6b Beleg-Prüfung: {confirmed}/{len(results)} Maßnahmen unabhängig bestätigt",
            ),
        }

    return check_evidence


# ---------------------------------------------------------------------------
# Knoten 7 – Freigabe (interrupt / Command)
# ---------------------------------------------------------------------------


def approval_gate(state: AgentState) -> Command:
    """Schritt 7: Der Graph hält an. Der Mensch entscheidet. Empfehlen ≠ Ausführen."""
    settings = _get_settings()
    audit = AuditLog(settings.audit_log_path)
    decision = interrupt(
        {
            "question": "Maßnahmen freigeben?",
            "actions": state.get("actions", []),
            "impact": state.get("impact", {}),
            "hypothesis": state.get("hypothesis", {}),
            "judge_results": state.get("judge_results", []),
        }
    )
    audit.record("approval", decision=decision, line_id=state.get("line_id"))
    return Command(
        goto=END,
        update={"approval": decision, "trace": _log(state, "7 Freigabe erfasst")},
    )


# ---------------------------------------------------------------------------
# Graph-Builder
# ---------------------------------------------------------------------------


def _default_tools() -> _Tools:
    """Direktimport der MES/RAG-Funktionen für lokale Nutzung ohne MCP-Subprocess."""
    from production_agent.mcp.mes_server import (
        estimate_impact as _estimate_impact,
    )
    from production_agent.mcp.mes_server import (
        find_similar_incidents,
        get_active_alarms,
        get_line_status,
        get_production_plan,
    )
    from production_agent.mcp.rag_server import search_maintenance_docs

    return {
        "get_line_status": lambda **kw: get_line_status(**kw),
        "get_production_plan": lambda **kw: get_production_plan(**kw),
        "get_active_alarms": lambda **kw: get_active_alarms(**kw),
        "search_maintenance_docs": lambda **kw: search_maintenance_docs(**kw),
        "find_similar_incidents": lambda **kw: find_similar_incidents(**kw),
        "estimate_impact": lambda **kw: _estimate_impact(**kw),
    }


def build_tools_from_mcp(sim_now: str = "") -> _Tools:
    """Werkzeuge über das ECHTE MCP-Protokoll (fastmcp.Client, stdio-Subprozesse) statt In-Process.

    Ersetzt den kaputten `langchain-mcp-adapters` MultiServerMCPClient (Import-Konflikt mit mcp 2.x:
    `RequestContext`). fastmcp.Client ist die bereits getestete Protokollebene (test_mcp_protocol).
    Ein persistenter Client läuft in einem Hintergrund-Event-Loop; jede Werkzeugausführung ist ein
    echter Protokollaufruf. SIM_NOW wird den Subprozessen beim Start mitgegeben (Replay-Uhr).
    """
    import asyncio
    import os
    import sys
    import threading

    from fastmcp import Client

    env = {**os.environ}
    if sim_now:
        env["SIM_NOW"] = sim_now
    # sys.executable statt bare "python": nutzt denselben Interpreter (venv), robust auch dort, wo
    # kein "python" im PATH liegt (CI, reine python3-Systeme) – sonst FileNotFoundError beim Spawn.
    py = sys.executable or "python3"
    servers = {
        "mes": {"command": py, "args": ["-m", "production_agent.mcp.mes_server"], "env": env},
        "maintenance_docs": {
            "command": py,
            "args": ["-m", "production_agent.mcp.rag_server"],
            "env": env,
        },
    }

    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, daemon=True).start()

    def _run(coro):
        return asyncio.run_coroutine_threadsafe(coro, loop).result()

    def _wrap(client: Any, name: str):
        def _call(**kwargs: Any) -> str:
            result = _run(client.call_tool(name, kwargs))
            content = getattr(result, "content", None)
            return content[0].text if content else str(result)

        return _call

    # Ein Client JE Server: bei mehreren Servern präfixiert fastmcp die Werkzeugnamen
    # (mes_get_line_status …); der Graph erwartet die unpräfixierten Namen.
    tools: _Tools = {}
    for name, spec in servers.items():
        client = Client({"mcpServers": {name: spec}})
        _run(client.__aenter__())
        for tool in _run(client.list_tools()):
            tools[tool.name] = _wrap(client, tool.name)
    return tools


def build_graph(
    tools: _Tools | None = None,
    checkpoint_path: str | None = None,
    sim_now: str = "",
    llm=None,
    use_mcp: bool | None = None,
):
    """Graph kompilieren.

    Args:
        tools: Werkzeug-Dict {name: callable(**kwargs)->str}.
               None → echtes MCP-Protokoll (use_mcp/settings) oder direkter In-Process-Import.
        checkpoint_path: Pfad zur SQLite-Checkpointer-Datenbank (None → InMemory).
        sim_now: ISO-Timestamp der Replay-Uhr; wird als SIM_NOW gesetzt.
        llm: BaseChatModel für Knoten 4 und 6 (None → ChatAnthropic aus Settings).
             Alternativ: dict {"narrow_cause": Runnable, "derive_actions": Runnable}
             mit bereits gewrappten Chains (z. B. für Tests).
        use_mcp: True → Werkzeuge über das echte MCP-Protokoll (fastmcp.Client, stdio); None →
                 settings.mcp_via_protocol (Default False, In-Process – schneller/deterministisch
                 für Tests). Der Aufrufpfad ist gekapselt, das Ergebnis identisch.
    """
    if sim_now:
        os.environ["SIM_NOW"] = sim_now

    if tools is not None:
        resolved_tools = tools
    else:
        via_mcp = use_mcp if use_mcp is not None else _get_settings().mcp_via_protocol
        resolved_tools = build_tools_from_mcp(sim_now) if via_mcp else _default_tools()

    # LLM-Chains auflösen. Ohne explizites llm entscheidet LLM_MODE: mock → deterministisches
    # Mock-LLM (kein API-Schlüssel, für E2E/CI); live → ChatAnthropic aus den Settings.
    if llm is None and _get_settings().llm_mode == "mock":
        from production_agent.graph.mock_llm import mock_chains

        llm = mock_chains()
    if isinstance(llm, dict):
        chain_narrow = llm["narrow_cause"]
        chain_derive = llm["derive_actions"]
        chain_judge = llm.get("judge")
        if chain_judge is None:
            from production_agent.graph.mock_llm import mock_judge_chain

            chain_judge = mock_judge_chain()
    else:
        base_llm = llm
        judge_llm = llm
        if base_llm is None:
            from langchain_anthropic import ChatAnthropic

            settings = _get_settings()
            key = settings.anthropic_api_key.get_secret_value()
            base_llm = ChatAnthropic(model=settings.llm_model_main, api_key=key)
            # Judge nutzt bewusst ein EIGENES Modell (LLM_MODEL_JUDGE), getrennt von Knoten 4/6
            judge_llm = ChatAnthropic(model=settings.llm_model_judge, api_key=key)
        # include_raw=True: robust gegen als JSON-String kodierte Tool-Ergebnisse (nur live),
        # invoke_structured entschachtelt statt zu crashen (siehe graph/structured.py).
        chain_narrow = base_llm.with_structured_output(Hypothesis, include_raw=True)
        chain_derive = base_llm.with_structured_output(_ActionsOutput, include_raw=True)
        chain_judge = judge_llm.with_structured_output(JudgeVerdict, include_raw=True)

    g = StateGraph(AgentState)
    g.add_node("capture_status", _make_capture_status(resolved_tools))
    g.add_node("analyze_alarms", _make_analyze_alarms(resolved_tools))
    g.add_node("retrieve_knowledge", _make_retrieve_knowledge(resolved_tools))
    g.add_node("narrow_cause", _make_narrow_cause(chain_narrow))
    g.add_node("estimate_impact", _make_estimate_impact(resolved_tools))
    g.add_node("derive_actions", _make_derive_actions(chain_derive))
    g.add_node("check_evidence", _make_check_evidence(chain_judge))
    g.add_node("approval_gate", approval_gate)

    g.set_entry_point("capture_status")
    g.add_edge("capture_status", "analyze_alarms")
    g.add_edge("analyze_alarms", "retrieve_knowledge")  # immer_wissen_abrufen: true
    g.add_edge("retrieve_knowledge", "narrow_cause")
    g.add_edge("narrow_cause", "estimate_impact")
    g.add_edge("estimate_impact", "derive_actions")
    g.add_edge("derive_actions", "check_evidence")  # 6b: unabhängige Beleg-Prüfung vor der Freigabe
    g.add_edge("check_evidence", "approval_gate")

    if checkpoint_path is None:
        from langgraph.checkpoint.memory import InMemorySaver

        return g.compile(checkpointer=InMemorySaver())
    import sqlite3

    conn = sqlite3.connect(checkpoint_path, check_same_thread=False)
    return g.compile(checkpointer=SqliteSaver(conn))
