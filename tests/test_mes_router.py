"""Unit-Tests für api/mes_router.py – MES-Endpunkte liefern 200, Stream, Lineage."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def mes_db(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Temporäre Gold-DB aus dem Simulator."""
    tmp = tmp_path_factory.mktemp("router_gold")
    db_path = str(tmp / "mes.sqlite")
    from production_agent.data.simulator import generate, load_decisions, write_sqlite

    dec = load_decisions(str(ROOT / "decisions.yaml"))
    evs = generate(dec)
    write_sqlite(
        dec,
        evs,
        db_path,
        schema_path=str(ROOT / "src/production_agent/data/schema.sql"),
    )
    return db_path


@pytest.fixture(scope="module")
def mes_client(mes_db: str):
    """Minimal-FastAPI-App mit dem MES-Router (kein LangGraph-Graph nötig)."""
    os.environ["MES_DB_PATH"] = mes_db
    os.environ["AUDIT_LOG_PATH"] = str(Path(mes_db).parent / "audit.jsonl")
    from production_agent.config import get_settings

    get_settings.cache_clear()

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from production_agent.api.mes_router import router

    app = FastAPI()
    app.include_router(router)
    yield TestClient(app)

    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# /mes/line/{line_id}
# ---------------------------------------------------------------------------


def test_mes_line_gibt_200(mes_client) -> None:
    r = mes_client.get("/mes/line/L1")
    assert r.status_code == 200


def test_mes_line_enthaelt_linie(mes_client) -> None:
    data = mes_client.get("/mes/line/L1").json()
    assert data["line"] is not None
    assert data["line"]["line_id"] == "L1"


def test_mes_line_enthaelt_betriebsmittel(mes_client) -> None:
    data = mes_client.get("/mes/line/L1").json()
    assert len(data["equipment"]) > 0


def test_mes_line_unbekannt_gibt_404(mes_client) -> None:
    r = mes_client.get("/mes/line/X99")
    assert r.status_code == 404


# Regression (Live-Test): /mes/line MUSS den PackML-Zustand ZUR Replay-Zeit liefern (<= SIM_NOW),
# nicht den global jüngsten. Bei aktiver Störung ist die betroffene Station gestört, nicht "Execute".
_FAULT = {"Held", "Aborted", "Stopped", "Suspended"}


def _latest_event(mes_db: str) -> dict:
    import sqlite3

    conn = sqlite3.connect(f"file:{mes_db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT event_id, reason_code FROM downtime_events_gold "
            "WHERE line_id='L1' AND end_ts IS NOT NULL ORDER BY start_ts DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    return dict(row)


def test_mes_line_zeigt_stoerung_zur_replay_zeit(mes_client, mes_db) -> None:
    ev = _latest_event(mes_db)
    data = mes_client.get(f"/mes/line/L1?event_id={ev['event_id']}").json()
    assert data["sim_now"], "Replay-Uhr fehlt in der Antwort"
    assert data["active_event"] and data["active_event"]["event_id"] == ev["event_id"]
    faulted = [e for e in data["equipment"] if e.get("packml_state") in _FAULT]
    assert faulted, "keine gestörte Station zur Replay-Zeit – Endpunkt filtert nicht nach SIM_NOW"
    # nicht alle Stationen 'Execute' (genau der Live-Test-Bug)
    assert not all(e.get("packml_state") == "Execute" for e in data["equipment"])
    # gestörte Station trägt die Verknüpfung zum aktiven Ereignis
    assert faulted[0].get("alarm", {}).get("event_id") == ev["event_id"]


def test_mes_line_default_nutzt_juengste_replay_zeit(mes_client, mes_db) -> None:
    ev = _latest_event(mes_db)
    data = mes_client.get("/mes/line/L1").json()  # ohne event_id → jüngstes Ereignis
    assert data["sim_now"]
    assert data["active_event"] and data["active_event"]["event_id"] == ev["event_id"]
    assert any(e.get("packml_state") in _FAULT for e in data["equipment"])


# ---------------------------------------------------------------------------
# /mes/events
# ---------------------------------------------------------------------------


def test_mes_events_gibt_200(mes_client) -> None:
    r = mes_client.get("/mes/events")
    assert r.status_code == 200


def test_mes_events_gibt_liste(mes_client) -> None:
    data = mes_client.get("/mes/events").json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_mes_events_enthaelt_pflichtfelder(mes_client) -> None:
    events = mes_client.get("/mes/events").json()
    first = events[0]
    for field in ("event_id", "start_ts", "packml_state", "reason_code"):
        assert field in first, f"Pflichtfeld '{field}' fehlt"


def test_mes_events_limit_parameter(mes_client) -> None:
    data = mes_client.get("/mes/events?limit=3").json()
    # run_readonly fügt ggf. eine _truncated-Zeile hinzu → filtern
    real = [r for r in data if "_truncated" not in r]
    assert len(real) <= 3


# ---------------------------------------------------------------------------
# /mes/lineage/{event_id}
# ---------------------------------------------------------------------------


def test_mes_lineage_gibt_200(mes_client) -> None:
    r = mes_client.get("/mes/lineage/1")
    assert r.status_code == 200


def test_mes_lineage_enthaelt_bronze_ids(mes_client) -> None:
    data = mes_client.get("/mes/lineage/1").json()
    assert "bronze_ids" in data
    assert len(data["bronze_ids"]) > 0


def test_mes_lineage_nur_eigene_bronze_ids(mes_client) -> None:
    """Falsifikation: Lineage für Ereignis 1 enthält keine fremden Bronze-IDs."""
    data = mes_client.get("/mes/lineage/1").json()
    for bid in data["bronze_ids"]:
        assert bid.startswith("sim:1:"), f"Fremde Bronze-ID: {bid}"


def test_mes_lineage_unbekannt_gibt_404(mes_client) -> None:
    r = mes_client.get("/mes/lineage/999999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# /mes/stream (SSE – mit speed-Parameter zum sofortigen Abbruch)
# ---------------------------------------------------------------------------


def test_mes_stream_gibt_200(mes_client) -> None:
    """SSE-Endpunkt antwortet mit 200 und text/event-stream."""
    with mes_client.stream("GET", "/mes/stream?speed=999999") as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")


def test_mes_stream_liefert_alarm_code(mes_client) -> None:
    """SSE-Stream enthält mindestens eine Zeile mit alarm_code."""
    lines: list[str] = []
    with mes_client.stream("GET", "/mes/stream?speed=999999") as r:
        for chunk in r.iter_lines():
            if chunk.startswith("data: "):
                lines.append(chunk[6:])
                if len(lines) >= 3:
                    break
    assert len(lines) > 0, "Kein SSE-Event empfangen"
    ev = json.loads(lines[0])
    assert "alarm_code" in ev
    assert ev["alarm_code"] == "E-4711"


# ---------------------------------------------------------------------------
# Simulator --stream (Subprocess-Test)
# ---------------------------------------------------------------------------


def test_simulator_stream_gibt_json_aus() -> None:
    """python -m production_agent.data.simulator --stream --speed 999999 → JSON-Zeilen."""
    result = subprocess.run(
        [sys.executable, "-m", "production_agent.data.simulator", "--stream", "--speed", "999999"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(ROOT),
    )
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lines) > 0, f"Kein Output; stderr={result.stderr[:400]}"
    first = json.loads(lines[0])
    assert first["alarm_code"] == "E-4711"


def test_simulator_stream_gibt_gueltiges_topic_aus() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "production_agent.data.simulator", "--stream", "--speed", "999999"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(ROOT),
    )
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lines) > 0
    for ln in lines[:5]:
        ev = json.loads(ln)
        parts = ev["topic"].split("/")
        assert parts[0] == "plant" and len(parts) == 4 and parts[3] == "alarm"
