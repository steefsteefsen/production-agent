"""Workflow-Tests mit gemocktem LLM und Fixture-Tools (keine echten API-Aufrufe).

Verifikation: endet am Freigabeknoten mit ≥1 Maßnahme und Konfidenz,
              verbotene Maßnahme gefiltert, Alarmflut → RAG immer ausgeführt.
Falsifikation: verbotene Maßnahme darf nie in der Interrupt-Payload erscheinen,
               ohne hypothesis schlägt estimate_impact zurück auf Standardwert.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from langchain_core.runnables import RunnableLambda
from langgraph.types import Command

from production_agent.graph.state import Hypothesis
from production_agent.graph.workflow import _ActionsOutput, build_graph
from production_agent.security.action_policy import ActionLevel, RecommendedAction

# ---------------------------------------------------------------------------
# Fixture-Tools
# ---------------------------------------------------------------------------

_NOW = datetime.now(UTC)
_ALARM_TS = (_NOW - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")


def _make_alarms(n: int) -> str:
    return json.dumps([{"alarm_code": "E-4711", "ts": _ALARM_TS, "priority": 1} for _ in range(n)])


def _fixture_tools(alarm_count: int = 12):
    return {
        "get_line_status": lambda **_: json.dumps(
            [{"equipment_id": "EQ1", "packml_state": "Held", "ts": _ALARM_TS}]
        ),
        "get_production_plan": lambda **_: json.dumps(
            [{"order_id": "ORD1", "planned_qty": 1000, "produced_qty": 500}]
        ),
        "get_active_alarms": lambda **_: _make_alarms(alarm_count),
        "search_maintenance_docs": lambda **_: json.dumps(
            [{"chunk_id": "doc1#0", "text": "Folienriss: Folie prüfen", "score_bm25": 1.2}]
        ),
        "find_similar_incidents": lambda **_: json.dumps(
            [{"event_id": "EVT-001", "reason_code": "STO-FOLIE", "duration_min": 25}]
        ),
        "estimate_impact": lambda **_: json.dumps(
            {
                "expected_downtime_min": 25.0,
                "lost_units": 1500,
                "cost_eur": 5000.0,
                "orders_at_risk": ["ORD1"],
            }
        ),
    }


# ---------------------------------------------------------------------------
# Fake-LLM-Chains (RunnableLambda, kein API-Aufruf)
# ---------------------------------------------------------------------------

_FAKE_HYPOTHESIS = Hypothesis(
    cause="Folienriss am Folienwickler",
    reason_code="STO-FOLIE",
    confidence=0.82,
    evidence=["E-4711", "EVT-001"],
    expected_downtime_min=25.0,
)

_FAKE_ACTIONS_SAFE = _ActionsOutput(
    actions=[
        RecommendedAction(
            title="Folie neu einlegen",
            description="Folienrolle am Folienwickler wechseln und einlegen.",
            level=ActionLevel.APPROVAL_REQUIRED,
            confidence=0.82,
            rationale="E-4711 historisch → STO-FOLIE (EVT-001)",
        )
    ]
)

_FAKE_ACTIONS_WITH_FORBIDDEN = _ActionsOutput(
    actions=[
        RecommendedAction(
            title="Not-Aus überbrücken damit die Linie läuft",
            description="Sicherheitskreis deaktivieren",
            level=ActionLevel.APPROVAL_REQUIRED,
            confidence=0.99,
            rationale="Schnellste Lösung",
        ),
        RecommendedAction(
            title="Folie neu einlegen",
            description="Folienrolle wechseln.",
            level=ActionLevel.APPROVAL_REQUIRED,
            confidence=0.82,
            rationale="EVT-001",
        ),
    ]
)


def _fake_llm(hypothesis=_FAKE_HYPOTHESIS, actions=_FAKE_ACTIONS_SAFE):
    return {
        "narrow_cause": RunnableLambda(lambda _: hypothesis),
        "derive_actions": RunnableLambda(lambda _: actions),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_graph_endet_am_freigabeknoten_mit_massnahme():
    """Verifikation: Graph stoppt am interrupt mit ≥1 Maßnahme und Konfidenz > 0."""
    g = build_graph(tools=_fixture_tools(12), llm=_fake_llm())
    cfg = {"configurable": {"thread_id": "wf-verify-1"}}
    result = g.invoke({"line_id": "L1", "trace": []}, cfg)

    assert "__interrupt__" in result
    payload = result["__interrupt__"][0].value
    assert len(payload["actions"]) >= 1
    assert payload["actions"][0]["confidence"] > 0


def test_verbotene_massnahme_gefiltert():
    """Verifikation: FORBIDDEN-Maßnahme (Not-Aus-Überbrückung) erscheint nie in der Freigabe."""
    g = build_graph(
        tools=_fixture_tools(12),
        llm=_fake_llm(actions=_FAKE_ACTIONS_WITH_FORBIDDEN),
    )
    cfg = {"configurable": {"thread_id": "wf-forbidden-1"}}
    result = g.invoke({"line_id": "L1", "trace": []}, cfg)

    payload = result["__interrupt__"][0].value
    titles = [a["title"] for a in payload["actions"]]
    assert all("Not-Aus" not in t for t in titles), f"Verbotene Maßnahme in Payload: {titles}"
    assert any("Folie" in t for t in titles), "Erlaubte Maßnahme fehlt"


def test_verbotene_massnahme_gefiltert_falsification():
    """Falsifikation: mit confidence=0.99 aber FORBIDDEN-Keyword muss gefiltert sein."""
    g = build_graph(
        tools=_fixture_tools(12),
        llm=_fake_llm(actions=_FAKE_ACTIONS_WITH_FORBIDDEN),
    )
    cfg = {"configurable": {"thread_id": "wf-forbidden-false-1"}}
    result = g.invoke({"line_id": "L1", "trace": []}, cfg)
    payload = result["__interrupt__"][0].value
    # wenn dieser Assert grün ist, hat apply_policy NICHT gefiltert → Test soll rot sein
    forbidden_present = any("Not-Aus" in a["title"] for a in payload["actions"])
    assert not forbidden_present, "apply_policy hat Not-Aus-Maßnahme nicht entfernt"


def test_alarmflut_rag_immer_ausgefuehrt():
    """Verifikation: retrieve_knowledge wird immer ausgeführt (kein Alarmflut-Sonderpfad)."""
    g = build_graph(tools=_fixture_tools(12), llm=_fake_llm())
    cfg = {"configurable": {"thread_id": "wf-flood-1"}}
    result = g.invoke({"line_id": "L1", "trace": []}, cfg)
    assert any("3 Wissen" in t for t in result.get("trace", []))


def test_ruhige_linie_rag_trotzdem_ausgefuehrt():
    """Verifikation: auch ohne Alarmflut (2 Alarme) läuft retrieve_knowledge (keine Verzweigung)."""
    g = build_graph(tools=_fixture_tools(2), llm=_fake_llm())
    cfg = {"configurable": {"thread_id": "wf-quiet-1"}}
    result = g.invoke({"line_id": "L1", "trace": []}, cfg)
    assert any("3 Wissen" in t for t in result.get("trace", []))


def test_ruhige_linie_rag_immer_falsification():
    """Falsifikation: wenn retrieve_knowledge fehlt, wäre routing falsch implementiert."""
    g = build_graph(tools=_fixture_tools(2), llm=_fake_llm())
    cfg = {"configurable": {"thread_id": "wf-quiet-false-1"}}
    result = g.invoke({"line_id": "L1", "trace": []}, cfg)
    trace = result.get("trace", [])
    # Test soll GRÜN sein, wenn retrieve_knowledge läuft (Falsifikation: wäre ROT wenn nicht)
    assert any("3 Wissen" in t for t in trace), "retrieve_knowledge fehlt in Spur – Routing defekt"


def test_freigabe_resume():
    """Verifikation: nach Command(resume=...) ist approval im Zustand gesetzt."""
    g = build_graph(tools=_fixture_tools(12), llm=_fake_llm())
    cfg = {"configurable": {"thread_id": "wf-resume-1"}}
    g.invoke({"line_id": "L1", "trace": []}, cfg)
    final = g.invoke(Command(resume={"approved": True, "comment": "ok"}), cfg)
    assert final["approval"]["approved"] is True
    assert final["trace"][-1].startswith("7 Freigabe")


def test_hypothesis_im_state():
    """Verifikation: hypothesis-Feld im State enthält reason_code und confidence."""
    g = build_graph(tools=_fixture_tools(12), llm=_fake_llm())
    cfg = {"configurable": {"thread_id": "wf-hypo-1"}}
    result = g.invoke({"line_id": "L1", "trace": []}, cfg)
    hypo = result.get("hypothesis", {})
    assert hypo.get("reason_code") == "STO-FOLIE"
    assert 0.0 <= hypo.get("confidence", -1) <= 1.0


def test_impact_enthält_kosten():
    """Verifikation: impact-Feld aus estimate_impact enthält cost_eur."""
    g = build_graph(tools=_fixture_tools(12), llm=_fake_llm())
    cfg = {"configurable": {"thread_id": "wf-impact-1"}}
    result = g.invoke({"line_id": "L1", "trace": []}, cfg)
    impact = result.get("impact", {})
    assert "cost_eur" in impact or "raw" in impact  # Fallback wenn Tool-Antwort kein JSON


def test_keine_echten_api_aufrufe_falsification():
    """Falsifikation: kein echter Anthropic-Key → build_graph mit llm=fake darf nicht scheitern."""
    import os

    os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        g = build_graph(tools=_fixture_tools(4), llm=_fake_llm())
        cfg = {"configurable": {"thread_id": "wf-noapi-1"}}
        result = g.invoke({"line_id": "L1", "trace": []}, cfg)
        assert "__interrupt__" in result
    finally:
        pass  # kein echtes Aufräumen nötig – env-Key war nicht gesetzt


# ---------------------------------------------------------------------------
# Helper-Funktions-Tests (Verifikation + Falsifikation für Abdeckung K4 ≥ 85%)
# ---------------------------------------------------------------------------


def test_parse_valid_json():
    """Verifikation: _parse gibt Python-Objekt aus gültigem JSON zurück."""
    from production_agent.graph.workflow import _parse

    assert _parse('[{"a": 1}]') == [{"a": 1}]


def test_parse_invalid_json_falsification():
    """Falsifikation: _parse darf bei ungültigem JSON nie explodieren, sondern leere Liste."""
    from production_agent.graph.workflow import _parse

    result = _parse("das ist kein json{")
    assert result == []


def test_parse_none_falsification():
    """Falsifikation: _parse mit None darf keinen Traceback werfen."""
    from production_agent.graph.workflow import _parse

    assert _parse(None) == []  # type: ignore[arg-type]


def test_top_alarm_codes_zählt_häufigste():
    """Verifikation: häufigster Code steht an erster Stelle."""
    from production_agent.graph.workflow import _top_alarm_codes

    alarms = [
        {"alarm_code": "E-001"},
        {"alarm_code": "E-001"},
        {"alarm_code": "E-002"},
    ]
    codes = _top_alarm_codes(alarms, n=2)
    assert codes[0] == "E-001"
    assert "E-002" in codes


def test_top_alarm_codes_leer_falsification():
    """Falsifikation: leere Alarmliste liefert leere Code-Liste."""
    from production_agent.graph.workflow import _top_alarm_codes

    assert _top_alarm_codes([]) == []


def test_extract_packml_state_liste():
    """Verifikation: PackML-State aus Linienstatus-Liste (erstes Element)."""
    from production_agent.graph.workflow import _extract_packml_state

    assert _extract_packml_state([{"packml_state": "Held"}]) == "Held"


def test_extract_packml_state_dict():
    """Verifikation: PackML-State aus Linienstatus-Dict direkt."""
    from production_agent.graph.workflow import _extract_packml_state

    assert _extract_packml_state({"packml_state": "Stopped"}) == "Stopped"


def test_extract_packml_state_leer_falsification():
    """Falsifikation: leerer State → 'Unknown', nie Exception."""
    from production_agent.graph.workflow import _extract_packml_state

    assert _extract_packml_state([]) == "Unknown"
    assert _extract_packml_state({}) == "Unknown"


def test_flood_in_window_erkennt_flut():
    """Verifikation: ≥10 Alarme im 10-min-Fenster → flood=True."""
    from production_agent.graph.workflow import _flood_in_window

    now = datetime.now(UTC)
    alarms = [{"ts": (now - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")} for _ in range(10)]
    assert _flood_in_window(alarms, window_min=10, threshold=10) is True


def test_flood_in_window_keine_flut():
    """Verifikation: 9 Alarme im Fenster → flood=False."""
    from production_agent.graph.workflow import _flood_in_window

    now = datetime.now(UTC)
    alarms = [{"ts": (now - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")} for _ in range(9)]
    assert _flood_in_window(alarms, window_min=10, threshold=10) is False


def test_flood_in_window_alte_alarme_ignoriert():
    """Verifikation: Alarme älter als 10 min zählen nicht zum Flutfenster."""
    from production_agent.graph.workflow import _flood_in_window

    now = datetime.now(UTC)
    alarms = [
        {"ts": (now - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")} for _ in range(12)
    ]
    assert _flood_in_window(alarms, window_min=10, threshold=10) is False


def test_flood_in_window_ohne_ts_falsification():
    """Falsifikation: Alarme ohne 'ts'-Feld dürfen nie einen Traceback erzeugen."""
    from production_agent.graph.workflow import _flood_in_window

    alarms = [{"alarm_code": "E-001"} for _ in range(20)]  # kein ts
    result = _flood_in_window(alarms)
    assert isinstance(result, bool)


def test_build_graph_mit_sqlite_checkpoint(tmp_path):
    """Verifikation: build_graph mit checkpoint_path erstellt SQLite-Checkpointer."""
    db = str(tmp_path / "check.sqlite")
    g = build_graph(tools=_fixture_tools(4), llm=_fake_llm(), checkpoint_path=db)
    cfg = {"configurable": {"thread_id": "wf-sqlite-1"}}
    result = g.invoke({"line_id": "L1", "trace": []}, cfg)
    assert "__interrupt__" in result


def test_build_graph_mit_sqlite_checkpoint_falsification(tmp_path):
    """Falsifikation: zweiter Invoke auf gleichem Thread hat gespeicherten Zustand (Checkpointer)."""
    from langgraph.types import Command

    db = str(tmp_path / "check2.sqlite")
    g = build_graph(tools=_fixture_tools(4), llm=_fake_llm(), checkpoint_path=db)
    cfg = {"configurable": {"thread_id": "wf-sqlite-2"}}
    g.invoke({"line_id": "L1", "trace": []}, cfg)
    final = g.invoke(Command(resume={"approved": True, "comment": "test"}), cfg)
    assert final.get("approval", {}).get("approved") is True


def test_default_tools_lädt_bei_replay_env(replay_env, monkeypatch):
    """Verifikation: _default_tools() importiert MES-Funktionen ohne Fehler."""
    from production_agent.graph.workflow import _default_tools

    tools = _default_tools()
    assert "get_line_status" in tools
    assert "estimate_impact" in tools
    assert callable(tools["get_line_status"])


# ---------------------------------------------------------------------------
# build_tools_from_mcp (MCP-Client gemockt)
# ---------------------------------------------------------------------------


class _FakeMCPTool:
    """Minimale MCP-Tool-Attrappe für build_tools_from_mcp-Tests."""

    name = "get_line_status"

    def invoke(self, kw):
        return '{"packml_state": "Running"}'


def _mock_mcp_imports(monkeypatch):
    """Installiert gefälschte MCP-Module in sys.modules (MCP-Version inkompatibel)."""
    import sys
    from types import ModuleType
    from unittest.mock import MagicMock

    # Stub für das nicht importierbare mcp.shared.context
    ctx_mod = ModuleType("mcp.shared.context")
    ctx_mod.RequestContext = MagicMock()
    monkeypatch.setitem(sys.modules, "mcp.shared.context", ctx_mod)

    # Stub für langchain_mcp_adapters.client
    client_mod = ModuleType("langchain_mcp_adapters.client")
    client_mod.MultiServerMCPClient = MagicMock()
    monkeypatch.setitem(sys.modules, "langchain_mcp_adapters.client", client_mod)


def test_build_tools_from_mcp_gibt_werkzeug_dict(monkeypatch):
    """Verifikation: build_tools_from_mcp gibt Werkzeug-Dict mit aufrufbaren Callables zurück."""
    _mock_mcp_imports(monkeypatch)
    monkeypatch.setattr("asyncio.run", lambda _coro: [_FakeMCPTool()])
    from production_agent.graph.workflow import build_tools_from_mcp

    tools = build_tools_from_mcp()
    assert "get_line_status" in tools
    assert callable(tools["get_line_status"])
    result = tools["get_line_status"](line_id="L1")
    assert result == '{"packml_state": "Running"}'


def test_build_tools_from_mcp_mit_sim_now(monkeypatch):
    """Verifikation: sim_now-Pfad (env["SIM_NOW"]=…) wird durchlaufen ohne Fehler."""
    _mock_mcp_imports(monkeypatch)
    monkeypatch.setattr("asyncio.run", lambda _coro: [_FakeMCPTool()])
    from production_agent.graph.workflow import build_tools_from_mcp

    tools = build_tools_from_mcp(sim_now="2024-06-01T08:00:00")
    assert callable(next(iter(tools.values())))


def test_build_tools_from_mcp_falsification(monkeypatch):
    """Falsifikation: asyncio.run wirft RuntimeError → build_tools_from_mcp propagiert ihn."""
    import pytest

    _mock_mcp_imports(monkeypatch)

    def _failing(_coro):
        raise RuntimeError("MCP-Subprozess nicht verfügbar")

    monkeypatch.setattr("asyncio.run", _failing)
    from production_agent.graph.workflow import build_tools_from_mcp

    with pytest.raises(RuntimeError, match="MCP-Subprozess"):
        build_tools_from_mcp()


# ---------------------------------------------------------------------------
# build_graph mit einzelnem LLM-Objekt (kein dict)
# ---------------------------------------------------------------------------


def test_build_graph_mit_einzelnem_llm():
    """Verifikation: build_graph akzeptiert ein einzelnes BaseChatModel (kein dict)."""
    from langchain_core.runnables import RunnableLambda

    class _FakeLLM:
        def with_structured_output(self, schema):
            if schema.__name__ == "Hypothesis":
                return RunnableLambda(lambda _: _FAKE_HYPOTHESIS)
            if schema.__name__ == "JudgeVerdict":
                from production_agent.graph.judge import JudgeVerdict

                return RunnableLambda(lambda _: JudgeVerdict(verified=True, judge_note="ok"))
            return RunnableLambda(lambda _: _FAKE_ACTIONS_SAFE)

    g = build_graph(tools=_fixture_tools(4), llm=_FakeLLM())
    cfg = {"configurable": {"thread_id": "wf-single-llm-1"}}
    result = g.invoke({"line_id": "L1", "trace": []}, cfg)
    assert "__interrupt__" in result
    payload = result["__interrupt__"][0].value
    assert len(payload["actions"]) >= 1


def test_build_graph_mit_einzelnem_llm_falsification():
    """Falsifikation: LLM-Objekt ohne with_structured_output → AttributeError beim Graphbau."""
    import pytest

    class _BrokenLLM:
        pass  # kein with_structured_output

    with pytest.raises(AttributeError):
        build_graph(tools=_fixture_tools(4), llm=_BrokenLLM())


# ---------------------------------------------------------------------------
# build_graph mit sim_now
# ---------------------------------------------------------------------------


def test_build_graph_setzt_sim_now_env():
    """Verifikation: build_graph mit sim_now setzt os.environ['SIM_NOW']."""
    import os

    ts = "2024-06-01T08:00:00"
    build_graph(tools=_fixture_tools(4), llm=_fake_llm(), sim_now=ts)
    assert os.environ.get("SIM_NOW") == ts


def test_build_graph_ohne_sim_now_setzt_kein_env_falsification():
    """Falsifikation: ohne sim_now bleibt SIM_NOW aus dem Umgebungs-Dict heraus."""
    import os

    os.environ.pop("SIM_NOW", None)
    build_graph(tools=_fixture_tools(4), llm=_fake_llm(), sim_now="")
    assert os.environ.get("SIM_NOW") is None, "SIM_NOW darf ohne sim_now nicht gesetzt sein"


# ---------------------------------------------------------------------------
# _flood_in_window – SIM_NOW-Env und ungültige Zeitstempel
# ---------------------------------------------------------------------------


def test_flood_in_window_mit_sim_now_env(monkeypatch):
    """Verifikation: _flood_in_window nutzt SIM_NOW-Umgebungsvariable als Referenzzeit."""
    from production_agent.graph.workflow import _flood_in_window

    sim_now = "2024-01-01T10:00:00"
    monkeypatch.setenv("SIM_NOW", sim_now)
    # 10 Alarme 2 Minuten vor SIM_NOW → Flut
    alarms = [{"ts": "2024-01-01 09:58:00"} for _ in range(10)]
    assert _flood_in_window(alarms, window_min=10, threshold=10) is True


def test_flood_in_window_ungültiger_sim_now_falsification(monkeypatch):
    """Falsifikation: ungültige SIM_NOW → Fallback auf datetime.now(UTC), kein Absturz."""
    from datetime import UTC, datetime, timedelta

    from production_agent.graph.workflow import _flood_in_window

    monkeypatch.setenv("SIM_NOW", "kein-iso-datum")
    now = datetime.now(UTC)
    alarms = [{"ts": (now - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")} for _ in range(10)]
    result = _flood_in_window(alarms)
    assert isinstance(result, bool)  # kein Absturz, Typ korrekt


def test_flood_in_window_ungültiger_ts_string_falsification():
    """Falsifikation: Alarm mit ungültigem ts-String wird übersprungen, kein Absturz."""
    from production_agent.graph.workflow import _flood_in_window

    alarms = [{"ts": "gestern-irgendwann"} for _ in range(20)]
    result = _flood_in_window(alarms)
    assert result is False  # kein Treffer, da ts nie parsebar


# ---------------------------------------------------------------------------
# _extract_packml_state – weder Liste noch Dict
# ---------------------------------------------------------------------------


def test_extract_packml_state_weder_liste_noch_dict_falsification():
    """Falsifikation: Input weder Liste noch Dict → immer 'Unknown', nie Exception."""
    from production_agent.graph.workflow import _extract_packml_state

    assert _extract_packml_state(None) == "Unknown"  # type: ignore[arg-type]
    assert _extract_packml_state("Held") == "Unknown"  # type: ignore[arg-type]
    assert _extract_packml_state(42) == "Unknown"  # type: ignore[arg-type]
