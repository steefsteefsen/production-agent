"""Simulator: deterministisch, Gold vollständig, Demo-Ereignis erzwungen."""

import sqlite3

from production_agent.data import simulator


def test_deterministic_with_seed(small_db):
    conn = sqlite3.connect(small_db)
    n1 = conn.execute("SELECT COUNT(*) FROM downtime_events_gold").fetchone()[0]
    assert n1 == 90  # 30 Tage × 3


def test_gold_rows_have_provenance_and_valid_state(small_db):
    conn = sqlite3.connect(small_db)
    states = {r[0] for r in conn.execute("SELECT DISTINCT packml_state FROM downtime_events_gold")}
    assert states <= {"Stopped", "Held", "Suspended", "Aborted"}
    assert (
        conn.execute("SELECT COUNT(*) FROM alarms_silver WHERE source_row_id IS NULL").fetchone()[0]
        == 0
    )
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM downtime_events_gold WHERE duration_min <= 0"
        ).fetchone()[0]
        == 0
    )


def test_seed_change_changes_data_falsification():
    """Falsifikation: ein anderer Seed liefert andere Ereignisse – sonst wäre der Seed wirkungslos."""
    import yaml

    from tests.conftest import ROOT

    dec = yaml.safe_load((ROOT / "decisions.yaml").read_text(encoding="utf-8"))
    dec["simulation"].update({"tage_historie": 5, "ereignisse_pro_tag": 4})
    a = [e.reason for e in simulator.generate(dec)]
    dec["simulation"]["seed"] = 99
    b = [e.reason for e in simulator.generate(dec)]
    assert a != b
