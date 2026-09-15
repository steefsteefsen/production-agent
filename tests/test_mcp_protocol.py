"""MCP-Ebene: die drei Server werden über das Protokoll (In-Memory-Client) getestet, nicht über
Python-Aufrufe. Verifikation: fachlich getrennte Werkzeuge (mes=3 Live, knowledge=3 Suche/Verlauf,
business_rules=1 Regel), jedes antwortet in der Daten-Hülle. Falsifikation: kein Schreib-/SQL-
Werkzeug, laufende Störung leckt nicht in die Historie, Zeilenlimit hält.
"""

from __future__ import annotations

import importlib
import json
import re

import pytest
from fastmcp import Client

pytestmark = pytest.mark.anyio


def body(result) -> list | dict:
    text = result.content[0].text
    return json.loads(re.search(r">\n(.*)\n</tool_data>", text, re.S).group(1))


async def _mes():
    from production_agent.mcp import mes_server

    importlib.reload(mes_server)
    return mes_server.mcp


async def _knowledge():
    from production_agent.mcp import rag_server

    importlib.reload(rag_server)
    return rag_server.mcp


async def _business():
    from production_agent.mcp import business_rules_server

    importlib.reload(business_rules_server)
    return business_rules_server.mcp


async def test_drei_fachlich_getrennte_server(replay_env):
    async with Client(await _mes()) as c:
        mes_names = {t.name for t in await c.list_tools()}
    async with Client(await _knowledge()) as c:
        know_names = {t.name for t in await c.list_tools()}
    async with Client(await _business()) as c:
        biz_names = {t.name for t in await c.list_tools()}
    assert mes_names == {"get_line_status", "get_active_alarms", "get_production_plan"}
    assert know_names == {"search_documents", "search_incidents", "get_alarm_history"}
    assert biz_names == {"estimate_impact"}
    # Falsifikation: nirgends ein freies SQL-/Schreib-Werkzeug
    for names in (mes_names, know_names, biz_names):
        assert not any(x in n for n in names for x in ("sql", "query", "write", "exec"))


async def test_every_tool_returns_untrusted_data_envelope(replay_env):
    mes_calls = {
        "get_line_status": {"line_id": "L1"},
        "get_active_alarms": {"line_id": "L1", "minutes": 30},
        "get_production_plan": {"line_id": "L1"},
    }
    know_calls = {
        "search_documents": {"query": "Folienriss"},
        "search_incidents": {"alarm_codes": ["E-4711"], "packml_state": "Held", "limit": 3},
        "get_alarm_history": {"alarm_code": "E-4711", "limit": 5},
    }
    biz_calls = {"estimate_impact": {"line_id": "L1", "expected_downtime_min": 15}}
    for server, calls, prefix in (
        (await _mes(), mes_calls, "mes"),
        (await _knowledge(), know_calls, "knowledge"),
        (await _business(), biz_calls, "business_rules"),
    ):
        async with Client(server) as c:
            for name, args in calls.items():
                r = await c.call_tool(name, args)
                text = r.content[0].text
                assert 'trusted="false"' in text, name
                assert f'source="{prefix}' in text, name


async def test_running_incident_never_leaks_into_history(replay_env):
    case = replay_env
    async with Client(await _mes()) as c:
        alarms = body(await c.call_tool("get_active_alarms", {"line_id": "L1", "minutes": 30}))
    assert alarms, "Gegenwart muss Alarme enthalten"
    first = alarms[-1]["alarm_code"]
    async with Client(await _knowledge()) as c:
        hist = body(await c.call_tool("get_alarm_history", {"alarm_code": first, "limit": 50}))
        sim = body(
            await c.call_tool(
                "search_incidents",
                {"alarm_codes": [first], "packml_state": "Held", "limit": 50},
            )
        )
    ids = {h.get("event_id") for h in hist} | {s.get("event_id") for s in sim}
    assert case.event_id not in ids  # Falsifikation: die verborgene Wahrheit bleibt verborgen


async def test_row_limit_is_hard(replay_env):
    async with Client(await _knowledge()) as c:
        r = body(await c.call_tool("get_alarm_history", {"alarm_code": "E-4711", "limit": 10_000}))
    assert len(r) <= 201
