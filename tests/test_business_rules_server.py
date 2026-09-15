"""business_rules-Server: estimate_impact – deterministische Wirkungsschätzung über FastMCP in-memory.

Verifikation: liefert Kosten, verlorene Einheiten und Pufferrechnung je Auftrag; die Methode ist
regelbasiert (kein Modell). Falsifikation: der at_risk-Flag stimmt mit buffer_min < 0 überein und
orders_at_risk ist eine Teilmenge der Aufträge (keine erfundenen Gefährdungen).

Fixture-DB: tests/fixtures/mes_fixture.sql. sim_now = '2026-06-15 10:00:00'
"""

from __future__ import annotations

import importlib
import json
import os
import re
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_SQL = ROOT / "tests/fixtures/mes_fixture.sql"
SCHEMA_SQL = ROOT / "src/production_agent/data/schema.sql"
SIM_NOW = "2026-06-15 10:00:00"

pytestmark = pytest.mark.anyio


def _body(result) -> dict:
    text = result.content[0].text
    return json.loads(re.search(r">\n(.*)\n</tool_data>", text, re.S).group(1))


@pytest.fixture
def fixture_env(tmp_path, monkeypatch):
    from production_agent.config import get_settings

    db = tmp_path / "mes.sqlite"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    conn.executescript(FIXTURES_SQL.read_text(encoding="utf-8"))
    conn.commit()
    conn.close()
    monkeypatch.setenv("MES_DB_PATH", str(db))
    monkeypatch.setenv("SIM_NOW", SIM_NOW)
    monkeypatch.setenv("AUDIT_LOG_PATH", str(tmp_path / "audit.jsonl"))
    get_settings.cache_clear()
    yield db
    get_settings.cache_clear()
    os.environ.pop("SIM_NOW", None)


async def _server():
    from production_agent.mcp import business_rules_server

    importlib.reload(business_rules_server)
    return business_rules_server.mcp


async def test_estimate_impact_liefert_kosten_und_puffer(fixture_env):
    """Verifikation: Kosten (EUR), verlorene Einheiten und je Auftrag ein Puffer; regelbasiert."""
    from fastmcp import Client

    async with Client(await _server()) as c:
        r = await c.call_tool("estimate_impact", {"line_id": "L1", "expected_downtime_min": 15})
        assert 'trusted="false"' in r.content[0].text
        assert 'source="business_rules' in r.content[0].text
    res = _body(r)
    assert res["cost_eur"] > 0
    assert res["lost_units"] > 0
    assert "regelbasiert" in res["method"]
    assert isinstance(res["orders"], list)


async def test_estimate_impact_at_risk_konsistent_falsification(fixture_env):
    """Falsifikation: at_risk == (buffer_min < 0) und orders_at_risk ⊆ orders (nichts erfunden)."""
    from fastmcp import Client

    async with Client(await _server()) as c:
        r = await c.call_tool("estimate_impact", {"line_id": "L1", "expected_downtime_min": 15})
    res = _body(r)
    order_ids = {o["order_id"] for o in res["orders"]}
    for o in res["orders"]:
        assert o["at_risk"] == (o["buffer_min"] < 0)
    assert set(res["orders_at_risk"]) <= order_ids
