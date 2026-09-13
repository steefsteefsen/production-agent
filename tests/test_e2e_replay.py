"""E2E-Replay-Test: der Graph läuft gegen die echten MES/RAG-Werkzeuge über den jüngsten Replay-Fall.

Verifikation: mock-Lauf liefert Exit 0 (ähnliche Vorfälle, belegte Maßnahme, Freigabeknoten, Ursache).
Falsifikation: ohne die <tool_data>-Auflösung in _parse käme kein Alarm an – der Lauf schlüge fehl.
Übersprungen, wenn keine Gold-Datenbank existiert (dann erst den Simulator laufen lassen)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from production_agent.config import get_settings  # noqa: E402

_DB = ROOT / get_settings().mes_db_path
pytestmark = pytest.mark.skipif(
    not _DB.exists(), reason="keine Gold-Datenbank – erst python -m production_agent.data.simulator"
)


def test_e2e_replay_mock_exit_null(monkeypatch):
    """Verifikation E1: der E2E-Replay im mock-Modus (Default-Fall 360) endet mit Exit 0."""
    monkeypatch.setenv("LLM_MODE", "mock")
    import e2e_replay

    assert e2e_replay.main([]) == 0


def test_e2e_zweiter_fall_andere_kategorie(monkeypatch):
    """E2: Prio-1-Fall 336 (STO-ANTRIEB) – andere Störungskategorie als STO-FOLIE, >5 min,
    ≥3 ähnliche Vorfälle. Gleiche Erwartungen wie E1: Ursache getroffen, Maßnahme belegt, ok."""
    monkeypatch.setenv("LLM_MODE", "mock")
    import e2e_replay

    s = e2e_replay.run(event_id=336, decision="none")
    assert s["ok"] is True
    assert s["reason_code"] == "STO-ANTRIEB" != "STO-FOLIE"
    assert s["reason_hit"] is True
    assert s["n_incidents"] >= 3  # genug historische Vorfälle für Case-Based Reasoning
    assert s["n_grounded"] >= 1  # mindestens eine Maßnahme mit Vorfall-ID belegt


def test_e2e_freigabepfad_approve(monkeypatch):
    """A2: nach interrupt() über den SQLite-Checkpointer fortsetzen, Freigabe erteilen →
    regulärer Abschluss, Freigabe=erteilt, Audit-Eintrag mit Rolle."""
    monkeypatch.setenv("LLM_MODE", "mock")
    import e2e_replay

    s = e2e_replay.run(decision="approve")
    assert s["ok"] is True
    assert s["interrupt_reached"] is True
    assert s["resumed_to_end"] is True
    assert s["approved"] is True
    assert s["audit_role"]  # rollenbasierter Audit-Eintrag


def test_e2e_ablehnungspfad_reject(monkeypatch):
    """A3: nach interrupt() fortsetzen, Freigabe verweigern → sauberer Abbruch ohne
    Maßnahmen-Abschluss (Freigabe=verweigert), Audit-Eintrag mit Rolle."""
    monkeypatch.setenv("LLM_MODE", "mock")
    import e2e_replay

    s = e2e_replay.run(decision="reject")
    assert s["ok"] is True
    assert s["interrupt_reached"] is True
    assert s["resumed_to_end"] is True
    assert s["approved"] is False
    assert s["audit_role"]


def test_e2e_determinismus_drei_laeufe(monkeypatch):
    """D1: drei mock-Läufe des Default-Falls sind bitidentisch (deterministisches Mock-LLM)."""
    import hashlib

    monkeypatch.setenv("LLM_MODE", "mock")
    import e2e_replay

    def _hash() -> str:
        s = e2e_replay.run(decision="none")
        return hashlib.sha256(json.dumps(s, sort_keys=True, default=str).encode()).hexdigest()

    hashes = {_hash() for _ in range(3)}
    assert len(hashes) == 1, f"nicht deterministisch: {hashes}"


def test_parse_loest_tool_data_huelle_falsification():
    """Falsifikation: _parse MUSS die <tool_data>-Hülle auflösen – täte es das nicht, käme aus den
    echten Werkzeugen eine leere Liste und der ganze E2E-Lauf bräche zusammen."""
    from production_agent.graph.workflow import _parse

    wrapped = '<tool_data source="mes.get_active_alarms" trusted="false">\n[{"alarm_code": "E-4711"}]\n</tool_data>'
    parsed = _parse(wrapped)
    assert parsed == [{"alarm_code": "E-4711"}]
    # ohne Hülle (Fixture-Form) weiterhin gültig
    assert _parse('[{"alarm_code": "E-4711"}]') == [{"alarm_code": "E-4711"}]
