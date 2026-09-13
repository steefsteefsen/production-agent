"""Gemeinsame Fixtures: kleine Simulator-DB, Replay-Uhr, aufzeichnende Werkzeuge (Trajektorie)."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest
import yaml

from production_agent.data import simulator

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _clear_sim_now_env():
    """build_graph(sim_now=…) setzt os.environ['SIM_NOW'] als Replay-Uhr für die MCP-Server. Nach jedem
    Test zurücksetzen, sonst leckt die Uhr in Folgetests (z. B. _flood_in_window)."""
    yield
    os.environ.pop("SIM_NOW", None)


@pytest.fixture(scope="session")
def small_db(tmp_path_factory) -> Path:
    """30 Tage Historie mit Seed 7 – klein, deterministisch, unabhängig von data/gold."""
    dec = yaml.safe_load((ROOT / "decisions.yaml").read_text(encoding="utf-8"))
    dec["simulation"].update({"seed": 7, "tage_historie": 30, "ereignisse_pro_tag": 3})
    db = tmp_path_factory.mktemp("db") / "mes.sqlite"
    simulator.write_sqlite(
        dec, simulator.generate(dec), db, ROOT / "src/production_agent/data/schema.sql"
    )
    return db


@pytest.fixture
def replay_env(small_db, monkeypatch):
    """Setzt MES_DB_PATH und SIM_NOW auf den jüngsten Fall und liefert den Fall zurück."""
    from production_agent.config import get_settings
    from production_agent.data.replay import select_replay_cases

    conn = sqlite3.connect(small_db)
    conn.row_factory = sqlite3.Row
    case = select_replay_cases(conn, n=1)[0]
    conn.close()
    monkeypatch.setenv("MES_DB_PATH", str(small_db))
    monkeypatch.setenv("SIM_NOW", case.now)
    monkeypatch.setenv("AUDIT_LOG_PATH", str(small_db.parent / "audit.jsonl"))
    get_settings.cache_clear()
    yield case
    get_settings.cache_clear()
    os.environ.pop("SIM_NOW", None)
