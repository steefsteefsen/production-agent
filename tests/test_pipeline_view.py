"""Unit-Tests für data/pipeline_view.py – Lineage, Bronze-IDs, Regel-Chips."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def mes_db(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Temporäre Gold-DB aus dem Simulator."""
    tmp = tmp_path_factory.mktemp("pview_gold")
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


def test_lineage_gibt_dict_zurueck(mes_db: str) -> None:
    from production_agent.data.pipeline_view import get_lineage

    lin = get_lineage(1, mes_db)
    assert lin is not None
    assert isinstance(lin, dict)


def test_lineage_pflichtfelder(mes_db: str) -> None:
    from production_agent.data.pipeline_view import get_lineage

    lin = get_lineage(1, mes_db)
    assert lin is not None
    for key in ("event_id", "bronze_ids", "silver_alarms", "rules_applied"):
        assert key in lin, f"Pflichtfeld '{key}' fehlt in Lineage"


def test_lineage_enthaelt_nur_eigene_bronze_ids(mes_db: str) -> None:
    """Alle Bronze-IDs der Lineage 1 müssen mit 'sim:1:' beginnen."""
    from production_agent.data.pipeline_view import get_lineage

    lin = get_lineage(1, mes_db)
    assert lin is not None
    assert len(lin["bronze_ids"]) > 0, "Keine Bronze-IDs in Lineage 1"
    for bid in lin["bronze_ids"]:
        assert bid.startswith("sim:1:"), f"Fremde Bronze-ID: {bid}"


def test_fremde_bronze_ids_nie_in_lineage_falsification(mes_db: str) -> None:
    """Falsifikation: Bronze-IDs anderer Ereignisse dürfen nicht in Lineage 1 auftauchen."""
    from production_agent.data.pipeline_view import get_lineage

    lin = get_lineage(1, mes_db)
    assert lin is not None
    fremd = [bid for bid in lin["bronze_ids"] if not bid.startswith("sim:1:")]
    assert fremd == [], f"Fremde Bronze-IDs gefunden: {fremd}"


def test_lineage_enthaelt_regel_chips(mes_db: str) -> None:
    from production_agent.data.pipeline_view import get_lineage

    lin = get_lineage(1, mes_db)
    assert lin is not None
    assert len(lin["rules_applied"]) >= 1


def test_lineage_silver_alarms_vorhanden(mes_db: str) -> None:
    from production_agent.data.pipeline_view import get_lineage

    lin = get_lineage(1, mes_db)
    assert lin is not None
    assert len(lin["silver_alarms"]) > 0


def test_lineage_unbekannte_id_gibt_none(mes_db: str) -> None:
    from production_agent.data.pipeline_view import get_lineage

    assert get_lineage(999_999, mes_db) is None


def test_lineage_mehrere_ereignisse_unabhaengig(mes_db: str) -> None:
    """Lineage für Ereignis 2 enthält keine Bronze-IDs aus Ereignis 1."""
    from production_agent.data.pipeline_view import get_lineage

    lin1 = get_lineage(1, mes_db)
    lin2 = get_lineage(2, mes_db)
    if lin1 is None or lin2 is None:
        pytest.skip("Weniger als 2 Ereignisse in Test-DB")
    ids1 = set(lin1["bronze_ids"])
    ids2 = set(lin2["bronze_ids"])
    overlap = ids1 & ids2
    assert not overlap, f"Überlappende Bronze-IDs: {overlap}"
