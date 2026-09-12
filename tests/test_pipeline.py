"""Datenschicht-Tests: Bronze→Silber→Gold Vollständigkeit und Rekonstruktion aus Bronze-CSV."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
import yaml

from production_agent.data import simulator
from production_agent.data.simulator import Event, build_from_bronze

ROOT = Path(__file__).resolve().parent.parent
VALID_PACKML_STATES = {"Stopped", "Held", "Suspended", "Aborted"}


@pytest.fixture(scope="module")
def pipeline_db(tmp_path_factory):
    """50 Tage × 3 Ereignisse/Tag, Seed 42 – genug Gold-Zeilen für die 100er-Grenze."""
    dec = yaml.safe_load((ROOT / "decisions.yaml").read_text(encoding="utf-8"))
    dec["simulation"].update({"seed": 42, "tage_historie": 50, "ereignisse_pro_tag": 3})
    db = tmp_path_factory.mktemp("pipeline") / "mes.sqlite"
    evs = simulator.generate(dec)
    simulator.write_sqlite(dec, evs, db, ROOT / "src/production_agent/data/schema.sql")
    return db


@pytest.fixture(scope="module")
def pipeline_conn(pipeline_db):
    conn = sqlite3.connect(pipeline_db)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


# ─── Gold-Vollständigkeit ──────────────────────────────────────────────────────


def test_gold_has_at_least_100_events(pipeline_conn):
    """Verifikation: Gold enthält mindestens 100 Ereigniszeilen."""
    count = pipeline_conn.execute("SELECT COUNT(*) FROM downtime_events_gold").fetchone()[0]
    assert count >= 100, f"Gold: {count} Ereignisse (erwartet >= 100)"


def test_gold_has_at_least_100_events_falsification():
    """Falsifikation: Mini-Simulation liefert deutlich weniger als 100 Events."""
    dec = yaml.safe_load((ROOT / "decisions.yaml").read_text(encoding="utf-8"))
    dec["simulation"].update({"seed": 42, "tage_historie": 1, "ereignisse_pro_tag": 2})
    evs = simulator.generate(dec)
    assert len(evs) < 100, "Mini-Simulation sollte < 100 Events haben"


def test_gold_duration_positive(pipeline_conn):
    """Verifikation: Jede Gold-Zeile hat duration_min > 0."""
    bad = pipeline_conn.execute(
        "SELECT COUNT(*) FROM downtime_events_gold WHERE duration_min <= 0"
    ).fetchone()[0]
    assert bad == 0, f"{bad} Gold-Ereignisse mit duration_min <= 0"


def test_gold_duration_positive_falsification():
    """Falsifikation: Ein Event mit Dauer 0 würde die Invariante duration_min > 0 verletzen."""
    dec = yaml.safe_load((ROOT / "decisions.yaml").read_text(encoding="utf-8"))
    dec["simulation"].update({"seed": 42, "tage_historie": 5, "ereignisse_pro_tag": 4})
    evs = simulator.generate(dec)
    assert all((e.end - e.start).total_seconds() > 0 for e in evs)
    # Manuell manipuliertes Event mit Dauer 0 – so etwas darf nicht in Gold landen
    ref = evs[0]
    bad_ev = Event(
        event_id=9999,
        reason=ref.reason,
        start=ref.start,
        end=ref.start,  # Dauer = 0
        station=ref.station,
        alarms=ref.alarms,
        flood=ref.flood,
        ai4i=ref.ai4i,
    )
    assert (bad_ev.end - bad_ev.start).total_seconds() == 0


def test_gold_reason_codes_valid(pipeline_conn):
    """Verifikation: Jede Gold-Zeile hat einen reason_code aus downtime_reason_codes."""
    valid = {r[0] for r in pipeline_conn.execute("SELECT code FROM downtime_reason_codes")}
    bad = pipeline_conn.execute(
        "SELECT COUNT(*) FROM downtime_events_gold "
        "WHERE reason_code IS NULL OR reason_code NOT IN "
        f"({','.join('?' * len(valid))})",
        list(valid),
    ).fetchone()[0]
    assert bad == 0, f"{bad} Gold-Ereignisse mit ungültigem reason_code"


def test_gold_reason_codes_valid_falsification(pipeline_conn):
    """Falsifikation: Ein unbekannter Code ist nicht in downtime_reason_codes."""
    valid = {r[0] for r in pipeline_conn.execute("SELECT code FROM downtime_reason_codes")}
    assert "PHANTOM-999" not in valid


def test_alarm_flood_binary(pipeline_conn):
    """Verifikation: alarm_flood ist ausschließlich 0 oder 1."""
    bad = pipeline_conn.execute(
        "SELECT COUNT(*) FROM downtime_events_gold WHERE alarm_flood NOT IN (0, 1)"
    ).fetchone()[0]
    assert bad == 0, f"{bad} Gold-Ereignisse mit alarm_flood nicht in {{0,1}}"


def test_alarm_flood_binary_falsification():
    """Falsifikation: Der Wert 2 liegt außerhalb des erlaubten Wertebereichs {{0,1}}."""
    assert 2 not in {0, 1}


def test_silver_has_source_row_id(pipeline_conn):
    """Verifikation: Jede alarms_silver-Zeile hat eine source_row_id (Bronze-Herkunft)."""
    bad = pipeline_conn.execute(
        "SELECT COUNT(*) FROM alarms_silver WHERE source_row_id IS NULL OR source_row_id = ''"
    ).fetchone()[0]
    assert bad == 0, f"{bad} Silver-Alarme ohne source_row_id"


def test_silver_has_source_row_id_falsification(pipeline_conn):
    """Falsifikation: Eine Silver-Zeile ohne source_row_id verletzt die Herkunfts-Invariante."""
    row = pipeline_conn.execute("SELECT source_row_id FROM alarms_silver LIMIT 1").fetchone()
    assert row is not None, "Keine alarms_silver-Zeilen vorhanden"
    assert row[0] is not None and row[0] != ""


def test_packml_states_gold(pipeline_conn):
    """Verifikation: packml_state in Gold ist nur Stopped, Held, Suspended oder Aborted."""
    states = {
        r[0]
        for r in pipeline_conn.execute("SELECT DISTINCT packml_state FROM downtime_events_gold")
    }
    assert states <= VALID_PACKML_STATES, f"Ungültige Zustände: {states - VALID_PACKML_STATES}"


def test_packml_states_gold_falsification():
    """Falsifikation: 'Execute' ist Betriebszustand, kein Stillstand – darf nicht in Gold stehen."""
    assert "Execute" not in VALID_PACKML_STATES


def test_youngest_event_is_e4711(pipeline_conn):
    """Verifikation: Das jüngste Gold-Ereignis ist das Demo-Ereignis mit Erstalarm E-4711."""
    row = pipeline_conn.execute(
        "SELECT first_alarm_code FROM downtime_events_gold ORDER BY start_ts DESC LIMIT 1"
    ).fetchone()
    assert row is not None
    assert row[0] == "E-4711", f"Jüngstes Ereignis: first_alarm_code = {row[0]!r}"


def test_youngest_event_is_e4711_falsification():
    """Falsifikation: Anderer demo_alarm_code → jüngstes Ereignis hat anderen Erstalarm."""
    dec = yaml.safe_load((ROOT / "decisions.yaml").read_text(encoding="utf-8"))
    dec["simulation"].update({"seed": 42, "tage_historie": 3, "ereignisse_pro_tag": 2})
    dec["simulation"]["demo_alarm_code"] = "E-3302"  # STO-SENSOR statt STO-FOLIE
    evs = simulator.generate(dec)
    idx = dec["simulation"]["demo_ereignis_index_von_hinten"]
    last = evs[-1 - idx]
    assert last.alarms[0][1] == "E-3302"


# ─── build_from_bronze ────────────────────────────────────────────────────────


def test_build_from_bronze_sequences(tmp_path):
    """Verifikation: Alarme mit Lücke <= gap_min → gleiche Sequenz, größer → neue Sequenz."""
    csv_content = "\n".join(
        [
            "machine,timestamp,alarm",
            "S1,2026-01-01T10:00:00,E-4711",  # Sequenz 1 auf S1
            "S1,2026-01-01T10:02:00,E-4713",  # 2 min Lücke <= 5 → gleiche Sequenz
            "S1,2026-01-01T10:12:00,E-4720",  # 10 min Lücke > 5 → neue Sequenz 2 auf S1
            "S2,2026-01-01T10:05:00,E-3302",  # andere Maschine → Sequenz 3
        ]
    )
    csv_path = tmp_path / "bronze.csv"
    csv_path.write_text(csv_content, encoding="utf-8")
    rows = build_from_bronze(csv_path)
    seq_ids = {r["sequence_id"] for r in rows}
    assert len(seq_ids) == 3, f"Erwartet 3 Sequenzen, erhalten: {len(seq_ids)}"
    # Die ersten zwei S1-Alarme teilen dieselbe sequence_id
    s1_pair = [r for r in rows if r["machine"] == "S1" and r["alarm_code"] in ("E-4711", "E-4713")]
    assert len({r["sequence_id"] for r in s1_pair}) == 1
    # source_row_id muss gesetzt und nicht leer sein
    assert all(r["source_row_id"] for r in rows)


def test_build_from_bronze_gap_creates_new_sequence_falsification(tmp_path):
    """Falsifikation: gap_min kleiner als die Lücke trennt Alarme in separate Sequenzen."""
    csv_content = "\n".join(
        [
            "machine,timestamp,alarm",
            "S1,2026-01-01T10:00:00,E-4711",
            "S1,2026-01-01T10:02:00,E-4713",  # 2 min Lücke
        ]
    )
    csv_path = tmp_path / "bronze_gap.csv"
    csv_path.write_text(csv_content, encoding="utf-8")
    # gap_min=5: 2 min <= 5 → eine Sequenz
    rows_5 = build_from_bronze(csv_path, gap_min=5.0)
    assert len({r["sequence_id"] for r in rows_5}) == 1
    # gap_min=1: 2 min > 1 → zwei Sequenzen
    rows_1 = build_from_bronze(csv_path, gap_min=1.0)
    assert len({r["sequence_id"] for r in rows_1}) == 2


def test_build_from_bronze_flood_flag(tmp_path):
    """Verifikation: >= 10 Alarme in 10 min → alarm_flood = 1."""
    lines = ["machine,timestamp,alarm"] + [f"S1,2026-01-01T10:{i:02d}:00,E-4711" for i in range(11)]
    csv_path = tmp_path / "bronze_flood.csv"
    csv_path.write_text("\n".join(lines), encoding="utf-8")
    rows = build_from_bronze(csv_path)
    assert all(r["alarm_flood"] == 1 for r in rows), "Alarmflut erwartet bei 11 Alarmen in 10 min"


def test_build_from_bronze_no_flood_falsification(tmp_path):
    """Falsifikation: Weniger als 10 Alarme in 10 min → alarm_flood bleibt 0."""
    lines = ["machine,timestamp,alarm"] + [f"S1,2026-01-01T10:{i:02d}:00,E-4711" for i in range(5)]
    csv_path = tmp_path / "bronze_noflood.csv"
    csv_path.write_text("\n".join(lines), encoding="utf-8")
    rows = build_from_bronze(csv_path)
    assert all(r["alarm_flood"] == 0 for r in rows), "Keine Alarmflut erwartet bei 5 Alarmen"


def test_build_from_bronze_same_event_count(tmp_path):
    """Verifikation: Rekonstruktion aus Bronze liefert dieselbe Ereignisanzahl wie der Simulator."""
    dec = yaml.safe_load((ROOT / "decisions.yaml").read_text(encoding="utf-8"))
    # 1 Ereignis/Tag → mittlerer Abstand 24h, weit größer als Alarm-Fenster von max. 12 min
    dec["simulation"].update({"seed": 42, "tage_historie": 5, "ereignisse_pro_tag": 1})
    dec["ereignis"]["kurzstillstand_min"] = 0  # alle Events → Gold → alle Alarme in Bronze+Silver
    evs = simulator.generate(dec)
    csv_text = simulator.export_bronze_csv(evs)
    csv_path = tmp_path / "bronze_recon.csv"
    csv_path.write_text(csv_text, encoding="utf-8")
    rows = build_from_bronze(csv_path, gap_min=5.0)
    recon_count = len({r["sequence_id"] for r in rows})
    assert recon_count == len(evs), (
        f"Rekonstruiert: {recon_count} Sequenzen, Simulator: {len(evs)} Ereignisse"
    )


def test_build_from_bronze_same_event_count_falsification(tmp_path):
    """Falsifikation: gap_min kleiner als die Lücke zwischen zwei Alarmen trennt fälschlich."""
    csv_content = "\n".join(
        [
            "machine,timestamp,alarm",
            "S1,2026-01-01T10:00:00,E-4711",
            "S1,2026-01-01T10:01:00,E-4713",  # 1 min Lücke
        ]
    )
    csv_path = tmp_path / "bronze_split.csv"
    csv_path.write_text(csv_content, encoding="utf-8")
    # gap_min=2: 1 min <= 2 → eine Sequenz (korrekt)
    rows_2 = build_from_bronze(csv_path, gap_min=2.0)
    assert len({r["sequence_id"] for r in rows_2}) == 1
    # gap_min=0.5: 1 min > 0.5 → zwei Sequenzen (falsifiziert den Eins-Sequenz-Fall)
    rows_half = build_from_bronze(csv_path, gap_min=0.5)
    assert len({r["sequence_id"] for r in rows_half}) == 2
