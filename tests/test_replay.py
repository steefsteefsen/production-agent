import sqlite3

from production_agent.data.replay import score, select_replay_cases


def test_replay_cases_hide_truth_and_shift_clock():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE downtime_events_gold (event_id INTEGER, line_id TEXT, start_ts TEXT, "
        "end_ts TEXT, duration_min REAL, reason_code TEXT, resolution_action TEXT, cost_eur REAL)"
    )
    for i in range(30):
        conn.execute(
            "INSERT INTO downtime_events_gold VALUES (?,?,?,?,?,?,?,?)",
            (
                i,
                "L1",
                f"2026-01-{i + 1:02d} 10:00:00",
                f"2026-01-{i + 1:02d} 10:30:00",
                30,
                "STO-MECH",
                "x",
                100,
            ),
        )
    cases = select_replay_cases(conn, n=3, offset_min=5, min_history=20)
    assert [c.event_id for c in cases] == [27, 28, 29]
    assert cases[0].now == "2026-01-28 10:05:00"
    assert cases[0].truth["reason_code"] == "STO-MECH"


def test_score():
    s = score(
        {"reason_code": "STO-MECH", "expected_downtime_min": 25},
        {"reason_code": "STO-MECH", "duration_min": 30},
    )
    assert s == {"reason_hit": True, "duration_abs_err_min": 5.0}


def test_replay_needs_history_falsification():
    """Falsifikation: ohne genug Historie gibt es keine Replay-Fälle – kein stilles Raten."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE downtime_events_gold (event_id INTEGER, line_id TEXT, start_ts TEXT, "
        "end_ts TEXT, duration_min REAL, reason_code TEXT, resolution_action TEXT, cost_eur REAL)"
    )
    for i in range(5):
        conn.execute(
            "INSERT INTO downtime_events_gold VALUES (?,?,?,?,?,?,?,?)",
            (i, "L1", f"2026-01-0{i + 1} 10:00:00", f"2026-01-0{i + 1} 10:30:00", 30, "X", "x", 1),
        )
    assert select_replay_cases(conn, n=3, min_history=20) == []
