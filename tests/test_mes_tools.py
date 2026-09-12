"""MES-Werkzeuge – Verifikations- und Falsifikationstests über FastMCP in-memory.

Jeder Block enthält je einen Verifikationstest (tut das Werkzeug das Richtige?)
und einen Falsifikationstest (bricht es, wenn eine Invariante verletzt ist?).
Falsifikationstests sind mit Suffix _falsification oder Kommentar gekennzeichnet.

Fixture-DB: tests/fixtures/mes_fixture.sql + 105 aktive Alarme (Python-Loop).
sim_now = '2026-06-15 10:00:00'
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


# ── Hilfsfunktionen ────────────────────────────────────────────────────────


def _body(result) -> list | dict:
    """Extrahiert den JSON-Inhalt aus der <tool_data>-Hülle."""
    text = result.content[0].text
    return json.loads(re.search(r">\n(.*)\n</tool_data>", text, re.S).group(1))


async def _server():
    from production_agent.mcp import mes_server

    importlib.reload(mes_server)  # Settings neu lesen (MES_DB_PATH, SIM_NOW)
    return mes_server.mcp


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def fixture_db(tmp_path_factory):
    """Lädt mes_fixture.sql + 105 aktive Alarme in eine temporäre SQLite-DB."""
    db = tmp_path_factory.mktemp("mes_fixture") / "mes.sqlite"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA_SQL.read_text(encoding="utf-8"))
    conn.executescript(FIXTURES_SQL.read_text(encoding="utf-8"))
    # 105 aktive Silber-Alarme (ts im 30-min-Fenster vor sim_now) für Limit-Test
    for i in range(1, 106):
        minute = 30 + i // 60
        second = i % 60
        ts = f"2026-06-15 09:{minute:02d}:{second:02d}"
        conn.execute(
            "INSERT INTO alarms_silver VALUES (?, 'L1-S1', ?, 'E-ACT', 3, 480, 1, ?)",
            (1000 + i, ts, f"fix:{i}"),
        )
    conn.commit()
    conn.close()
    return db


@pytest.fixture
def fixture_env(fixture_db, monkeypatch):
    """Setzt MES_DB_PATH, SIM_NOW und AUDIT_LOG_PATH für die kontrollierte Fixture-DB."""
    from production_agent.config import get_settings

    monkeypatch.setenv("MES_DB_PATH", str(fixture_db))
    monkeypatch.setenv("SIM_NOW", SIM_NOW)
    monkeypatch.setenv("AUDIT_LOG_PATH", str(fixture_db.parent / "audit.jsonl"))
    get_settings.cache_clear()
    yield fixture_db
    get_settings.cache_clear()
    os.environ.pop("SIM_NOW", None)


# ── Hülle: <tool_data trusted="false"> ────────────────────────────────────


async def test_alle_werkzeuge_liefern_untrusted_huelle(replay_env):
    """Verifikation: jedes Werkzeug verpackt sein Ergebnis in <tool_data trusted="false">."""
    from fastmcp import Client

    calls = {
        "get_line_status": {"line_id": "L1"},
        "get_active_alarms": {"line_id": "L1", "minutes": 30},
        "get_alarm_history": {"alarm_code": "E-4711", "limit": 5},
        "get_production_plan": {"line_id": "L1"},
        "estimate_impact": {"line_id": "L1", "expected_downtime_min": 15},
        "find_similar_incidents": {
            "alarm_codes": ["E-4711"],
            "packml_state": "Held",
            "limit": 3,
        },
    }
    async with Client(await _server()) as c:
        for name, args in calls.items():
            r = await c.call_tool(name, args)
            assert 'trusted="false"' in r.content[0].text, f"{name}: Hülle fehlt"


async def test_huelle_kein_rohes_json_falsification(replay_env):
    """Falsifikation: das Ergebnis ist KEIN reines JSON-Array (muss in Hülle stecken)."""
    from fastmcp import Client

    async with Client(await _server()) as c:
        r = await c.call_tool("get_line_status", {"line_id": "L1"})
    text = r.content[0].text
    # würde das Tool rohe JSON zurückgeben, begänne text mit '[' oder '{'
    assert not text.strip().startswith("["), "get_line_status gibt rohes JSON zurück (keine Hülle)"
    assert not text.strip().startswith("{"), "get_line_status gibt rohes JSON zurück (keine Hülle)"


# ── Audit-Eintrag ──────────────────────────────────────────────────────────


async def test_audit_eintrag_wird_geschrieben(fixture_env):
    """Verifikation: ein Werkzeugaufruf erzeugt einen Audit-Eintrag mit dem Werkzeugnamen."""
    from fastmcp import Client

    audit_path = fixture_env.parent / "audit.jsonl"
    audit_path.unlink(missing_ok=True)
    async with Client(await _server()) as c:
        await c.call_tool("get_line_status", {"line_id": "L1"})
    assert audit_path.exists()
    entries = [json.loads(line) for line in audit_path.read_text().splitlines() if line.strip()]
    assert any(e.get("tool") == "get_line_status" for e in entries)


async def test_kein_audit_vor_aufruf_falsification(fixture_env):
    """Falsifikation: vor dem Aufruf existiert kein Eintrag – das Audit wird also erst durch den Aufruf erzeugt."""
    from fastmcp import Client

    audit_path = fixture_env.parent / "audit.jsonl"
    audit_path.unlink(missing_ok=True)
    # Noch kein Aufruf → kein Eintrag
    assert not audit_path.exists() or audit_path.stat().st_size == 0
    async with Client(await _server()) as c:
        await c.call_tool("get_line_status", {"line_id": "L1"})
    # Nach dem Aufruf muss die Datei existieren und mindestens einen Eintrag enthalten
    assert audit_path.exists()
    assert audit_path.stat().st_size > 0


# ── get_line_status ────────────────────────────────────────────────────────


async def test_get_line_status_liefert_packml_zustand(fixture_env):
    """Verifikation: liefert den letzten PackML-Zustand aller Betriebsmittel (ts <= sim_now)."""
    from fastmcp import Client

    async with Client(await _server()) as c:
        r = await c.call_tool("get_line_status", {"line_id": "L1"})
    rows = _body(r)
    assert isinstance(rows, list)
    assert len(rows) > 0
    # Folienwickler muss 'Held' haben (laut Fixture: equipment_state at 09:55)
    held = [row for row in rows if row.get("equipment_id") == "L1-S1"]
    assert held and held[0]["packml_state"] == "Held"


async def test_get_line_status_unbekannte_linie_falsification(fixture_env):
    """Falsifikation: unbekannte Linie liefert leere Liste, nicht eine Zeile."""
    from fastmcp import Client

    async with Client(await _server()) as c:
        r = await c.call_tool("get_line_status", {"line_id": "GIBTS-NICHT"})
    rows = _body(r)
    assert rows == [], f"Erwarte [], bekam: {rows}"


# ── get_active_alarms ──────────────────────────────────────────────────────


async def test_get_active_alarms_liefert_alarme_im_fenster(fixture_env):
    """Verifikation: liefert Alarme, deren ts im Zeitfenster [sim_now-30min, sim_now] liegt."""
    from fastmcp import Client

    async with Client(await _server()) as c:
        r = await c.call_tool("get_active_alarms", {"line_id": "L1", "minutes": 30})
    rows = _body(r)
    real_rows = [row for row in rows if "_truncated" not in row]
    assert len(real_rows) > 0
    # Alle zurückgegebenen Zeitstempel müssen im Fenster liegen
    for row in real_rows:
        assert row["ts"] >= "2026-06-15 09:30:00", f"ts zu früh: {row['ts']}"
        assert row["ts"] <= SIM_NOW, f"ts nach sim_now: {row['ts']}"


async def test_get_active_alarms_limit_100_falsification(fixture_env):
    """Falsifikation: 105 Alarme im Fenster → maximal 100 dürfen zurückgegeben werden."""
    from fastmcp import Client

    async with Client(await _server()) as c:
        r = await c.call_tool("get_active_alarms", {"line_id": "L1", "minutes": 30})
    rows = _body(r)
    real_rows = [row for row in rows if "_truncated" not in row]
    assert len(real_rows) <= 100, f"Limit 100 verletzt: {len(real_rows)} Zeilen zurückgegeben"


# ── get_alarm_history ──────────────────────────────────────────────────────


async def test_get_alarm_history_liefert_historische_ereignisse(fixture_env):
    """Verifikation: liefert abgeschlossene Gold-Ereignisse für den gesuchten Alarmcode."""
    from fastmcp import Client

    async with Client(await _server()) as c:
        r = await c.call_tool("get_alarm_history", {"alarm_code": "E-TEST", "limit": 5})
    rows = _body(r)
    assert isinstance(rows, list)
    assert len(rows) > 0
    for row in rows:
        assert "event_id" in row


async def test_get_alarm_history_limit_20_falsification(fixture_env):
    """Falsifikation: 25 historische Ereignisse in DB → maximal 20 zurückgegeben (limit=100 ignoriert)."""
    from fastmcp import Client

    async with Client(await _server()) as c:
        r = await c.call_tool("get_alarm_history", {"alarm_code": "E-TEST", "limit": 100})
    rows = _body(r)
    real_rows = [row for row in rows if "_truncated" not in row]
    assert len(real_rows) <= 20, f"Limit 20 verletzt: {len(real_rows)} Zeilen zurückgegeben"


async def test_get_alarm_history_leck_test(fixture_env):
    """Falsifikation (Leck-Test): Ereignis mit end_ts > sim_now erscheint NICHT in der Historie."""
    from fastmcp import Client

    async with Client(await _server()) as c:
        # event_id=99 hat first_alarm_code='E-LEAK' und end_ts='2026-06-15 10:30:00' > sim_now
        r = await c.call_tool("get_alarm_history", {"alarm_code": "E-LEAK", "limit": 100})
    rows = _body(r)
    event_ids = {row.get("event_id") for row in rows if "_truncated" not in row}
    assert 99 not in event_ids, (
        "Leck! Laufendes Ereignis (event_id=99) erscheint in get_alarm_history"
    )


# ── get_production_plan ────────────────────────────────────────────────────


async def test_get_production_plan_liefert_offene_auftraege(fixture_env):
    """Verifikation: liefert offene Aufträge (produced_qty < planned_qty), sortiert nach Termin."""
    from fastmcp import Client

    async with Client(await _server()) as c:
        r = await c.call_tool("get_production_plan", {"line_id": "L1"})
    rows = _body(r)
    order_ids = {row.get("order_id") for row in rows}
    assert "A-AT-RISK" in order_ids
    assert "A-SAFE" in order_ids


async def test_get_production_plan_schliesst_abgeschlossene_aus_falsification(fixture_env):
    """Falsifikation: abgeschlossener Auftrag A-DONE (produced=planned) erscheint NICHT im Plan."""
    from fastmcp import Client

    async with Client(await _server()) as c:
        r = await c.call_tool("get_production_plan", {"line_id": "L1"})
    rows = _body(r)
    order_ids = {row.get("order_id") for row in rows}
    assert "A-DONE" not in order_ids, "Abgeschlossener Auftrag A-DONE erscheint fälschlich im Plan"


# ── estimate_impact ────────────────────────────────────────────────────────


async def test_estimate_impact_liefert_kosten_und_puffer(fixture_env):
    """Verifikation: Kosten = cost_rate × downtime, Puffer-Formel korrekt berechnet."""
    from fastmcp import Client

    async with Client(await _server()) as c:
        r = await c.call_tool("estimate_impact", {"line_id": "L1", "expected_downtime_min": 45})
    data = _body(r)
    # Kosten: 45 min × 200 €/min = 9000 €
    assert data["cost_eur"] == pytest.approx(9000.0)
    # Produktionsverlust: 45/60 × 3600 = 2700 Stück
    assert data["lost_units"] == 2700
    # Detailliste muss vorhanden sein
    assert "orders" in data
    assert isinstance(data["orders"], list)


async def test_estimate_impact_genau_ein_gefaehrdeter_auftrag_falsification(fixture_env):
    """Falsifikation: Pufferformel – bei expected_downtime_min=45 ist genau A-AT-RISK gefährdet.

    A-AT-RISK: buffer = (10:20-10:00) - (600/3600×60) - 45 = 20 - 10 - 45 = -35 min → at_risk
    A-SAFE:    buffer = (12:00-10:00) - (600/3600×60) - 45 = 120 - 10 - 45 = +65 min → sicher
    """
    from fastmcp import Client

    async with Client(await _server()) as c:
        r = await c.call_tool("estimate_impact", {"line_id": "L1", "expected_downtime_min": 45})
    data = _body(r)
    assert "orders_at_risk" in data, "Feld orders_at_risk fehlt"
    assert data["orders_at_risk"] == ["A-AT-RISK"], (
        f"Erwarte genau ['A-AT-RISK'], bekam: {data['orders_at_risk']}"
    )
    # Pufferwert für den gefährdeten Auftrag muss negativ sein
    at_risk_detail = next(o for o in data["orders"] if o["order_id"] == "A-AT-RISK")
    assert at_risk_detail["buffer_min"] < 0
    safe_detail = next(o for o in data["orders"] if o["order_id"] == "A-SAFE")
    assert safe_detail["buffer_min"] > 0


# ── find_similar_incidents ─────────────────────────────────────────────────


async def test_find_similar_incidents_liefert_aehnliche_faelle(fixture_env):
    """Verifikation: liefert historische Fälle mit passendem Alarmcode und PackML-Zustand."""
    from fastmcp import Client

    async with Client(await _server()) as c:
        r = await c.call_tool(
            "find_similar_incidents",
            {"alarm_codes": ["E-TEST"], "packml_state": "Held", "limit": 3},
        )
    rows = _body(r)
    assert isinstance(rows, list)
    assert len(rows) > 0
    for row in rows:
        assert "event_id" in row


async def test_find_similar_incidents_limit_5_falsification(fixture_env):
    """Falsifikation: 25 passende Ereignisse in DB → maximal 5 zurückgegeben (limit=100 ignoriert)."""
    from fastmcp import Client

    async with Client(await _server()) as c:
        r = await c.call_tool(
            "find_similar_incidents",
            {"alarm_codes": ["E-TEST"], "packml_state": "Held", "limit": 100},
        )
    rows = _body(r)
    real_rows = [row for row in rows if "_truncated" not in row]
    assert len(real_rows) <= 5, f"Limit 5 verletzt: {len(real_rows)} Zeilen zurückgegeben"


async def test_find_similar_incidents_leck_test(fixture_env):
    """Falsifikation (Leck-Test): Ereignis mit end_ts > sim_now erscheint NICHT in ähnlichen Fällen."""
    from fastmcp import Client

    async with Client(await _server()) as c:
        # event_id=99 hat first_alarm_code='E-LEAK' und end_ts > sim_now
        r = await c.call_tool(
            "find_similar_incidents",
            {"alarm_codes": ["E-LEAK"], "packml_state": "Held", "limit": 100},
        )
    rows = _body(r)
    event_ids = {row.get("event_id") for row in rows if "_truncated" not in row}
    assert 99 not in event_ids, (
        "Leck! Laufendes Ereignis (event_id=99) erscheint in find_similar_incidents"
    )
