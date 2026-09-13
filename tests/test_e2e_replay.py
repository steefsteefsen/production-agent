"""E2E-Replay-Test: der Graph läuft gegen die echten MES/RAG-Werkzeuge über den jüngsten Replay-Fall.

Verifikation: mock-Lauf liefert Exit 0 (ähnliche Vorfälle, belegte Maßnahme, Freigabeknoten, Ursache).
Falsifikation: ohne die <tool_data>-Auflösung in _parse käme kein Alarm an – der Lauf schlüge fehl.
Übersprungen, wenn keine Gold-Datenbank existiert (dann erst den Simulator laufen lassen)."""

from __future__ import annotations

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
    """Verifikation: der E2E-Replay im mock-Modus endet mit Exit 0."""
    monkeypatch.setenv("LLM_MODE", "mock")
    import e2e_replay

    assert e2e_replay.main() == 0


def test_parse_loest_tool_data_huelle_falsification():
    """Falsifikation: _parse MUSS die <tool_data>-Hülle auflösen – täte es das nicht, käme aus den
    echten Werkzeugen eine leere Liste und der ganze E2E-Lauf bräche zusammen."""
    from production_agent.graph.workflow import _parse

    wrapped = '<tool_data source="mes.get_active_alarms" trusted="false">\n[{"alarm_code": "E-4711"}]\n</tool_data>'
    parsed = _parse(wrapped)
    assert parsed == [{"alarm_code": "E-4711"}]
    # ohne Hülle (Fixture-Form) weiterhin gültig
    assert _parse('[{"alarm_code": "E-4711"}]') == [{"alarm_code": "E-4711"}]
