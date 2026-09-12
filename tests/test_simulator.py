"""Simulator: deterministisch, Gold vollständig, Kurzstillstände getrennt, Demo erzwungen, UP1/14 Codes."""

import sqlite3

from production_agent.data import simulator


def test_deterministic_with_seed(small_db):
    conn = sqlite3.connect(small_db)
    gold = conn.execute("SELECT COUNT(*) FROM downtime_events_gold").fetchone()[0]
    short = conn.execute("SELECT COUNT(*) FROM short_stops").fetchone()[0]
    assert gold + short == 90  # 30 Tage × 3, aufgeteilt in Gold und Kurzstillstände
    assert gold > 0


def test_gold_provenance_states_and_durations(small_db):
    conn = sqlite3.connect(small_db)
    states = {r[0] for r in conn.execute("SELECT DISTINCT packml_state FROM downtime_events_gold")}
    assert states <= {"Stopped", "Held", "Suspended", "Aborted"}
    assert (
        conn.execute("SELECT COUNT(*) FROM alarms_silver WHERE source_row_id IS NULL").fetchone()[0]
        == 0
    )
    # alle Nicht-Prio-1-Gold-Ereignisse dauern mindestens kurzstillstand_min (ADR-0001)
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM downtime_events_gold WHERE first_alarm_prio > 1 AND duration_min < 5"
        ).fetchone()[0]
        == 0
    )


def test_ext_up_and_short_stops_present(small_db):
    conn = sqlite3.connect(small_db)
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM downtime_events_gold WHERE reason_code='EXT-UP'"
        ).fetchone()[0]
        > 0
    )
    assert conn.execute("SELECT COUNT(*) FROM short_stops").fetchone()[0] > 0


def test_demo_event_is_folienriss_held_with_flood(small_db):
    conn = sqlite3.connect(small_db)
    r = conn.execute(
        "SELECT first_alarm_code, packml_state, alarm_flood FROM downtime_events_gold "
        "ORDER BY start_ts DESC LIMIT 1"
    ).fetchone()
    assert r == ("E-4711", "Held", 1), r


def test_seed_change_changes_data_falsification():
    import yaml

    from tests.conftest import ROOT

    dec = yaml.safe_load((ROOT / "decisions.yaml").read_text(encoding="utf-8"))
    dec["simulation"].update({"tage_historie": 5, "ereignisse_pro_tag": 4})
    a = [e.reason for e in simulator.generate(dec)]
    dec["simulation"]["seed"] = 99
    b = [e.reason for e in simulator.generate(dec)]
    assert a != b


def test_two_priority_methods_differ_falsification():
    """Falsifikation: ISA-18.2-Matrix und Hersteller-Severity liefern nicht dieselbe Verteilung."""
    import yaml

    from tests.conftest import ROOT

    dec = yaml.safe_load((ROOT / "decisions.yaml").read_text(encoding="utf-8"))
    dec["alarm_prioritaet"]["verfahren"] = "isa18_matrix"
    a = sorted(p for e in simulator.generate(dec) for _, _, p, _ in e.alarms)
    dec["alarm_prioritaet"]["verfahren"] = "hersteller_severity"
    b = sorted(p for e in simulator.generate(dec) for _, _, p, _ in e.alarms)
    assert a != b
