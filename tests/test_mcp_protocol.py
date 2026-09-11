"""MCP-Ebene: der Server wird über das Protokoll (In-Memory-Client) getestet, nicht über Python-Aufrufe.
Verifikation: 6 Werkzeuge, jedes antwortet in der Daten-Hülle. Falsifikation: kein Schreib-/SQL-Werkzeug,
laufende Störung leckt nicht in die Historie, Zeilenlimit hält."""

from __future__ import annotations

import json
import re

import pytest
from fastmcp import Client

pytestmark = pytest.mark.anyio


def body(result) -> list | dict:
    text = result.content[0].text
    return json.loads(re.search(r">\n(.*)\n</tool_data>", text, re.S).group(1))


async def _server():
    import importlib

    from production_agent.mcp import mes_server

    importlib.reload(mes_server)  # Settings neu lesen (MES_DB_PATH, SIM_NOW)
    return mes_server.mcp


async def test_exactly_six_domain_tools_and_no_sql_tool(replay_env):
    async with Client(await _server()) as c:
        names = {t.name for t in await c.list_tools()}
    assert names == {
        "get_line_status",
        "get_active_alarms",
        "get_alarm_history",
        "get_production_plan",
        "estimate_impact",
        "find_similar_incidents",
    }
    assert not any(n for n in names if "sql" in n or "query" in n or "write" in n)  # Falsifikation


async def test_every_tool_returns_untrusted_data_envelope(replay_env):
    calls = {
        "get_line_status": {"line_id": "L1"},
        "get_active_alarms": {"line_id": "L1", "minutes": 30},
        "get_alarm_history": {"alarm_code": "E-4711", "limit": 5},
        "get_production_plan": {"line_id": "L1"},
        "estimate_impact": {"line_id": "L1", "expected_downtime_min": 15},
        "find_similar_incidents": {"alarm_codes": ["E-4711"], "packml_state": "Held", "limit": 3},
    }
    async with Client(await _server()) as c:
        for name, args in calls.items():
            r = await c.call_tool(name, args)
            assert r.content[0].text.startswith('<tool_data source="mes.'), name
            assert 'trusted="false"' in r.content[0].text


async def test_running_incident_never_leaks_into_history(replay_env):
    case = replay_env
    async with Client(await _server()) as c:
        alarms = body(await c.call_tool("get_active_alarms", {"line_id": "L1", "minutes": 30}))
        assert alarms, "Gegenwart muss Alarme enthalten"
        first = alarms[-1]["alarm_code"]
        hist = body(await c.call_tool("get_alarm_history", {"alarm_code": first, "limit": 50}))
        sim = body(
            await c.call_tool(
                "find_similar_incidents",
                {"alarm_codes": [first], "packml_state": "Held", "limit": 50},
            )
        )
    ids = {h.get("event_id") for h in hist} | {s.get("event_id") for s in sim}
    assert case.event_id not in ids  # Falsifikation: die verborgene Wahrheit bleibt verborgen


async def test_row_limit_is_hard(replay_env):
    async with Client(await _server()) as c:
        r = body(await c.call_tool("get_alarm_history", {"alarm_code": "E-4711", "limit": 10_000}))
    assert len(r) <= 201
