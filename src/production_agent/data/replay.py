"""Replay: die Entscheidungsbasis wird nicht erfunden, sondern aus der Historie ausgeschnitten.

Ein Medallion, zwei Rollen:
  Historie  = alle Störungsereignisse, die VOR der Replay-Uhr abgeschlossen sind (Gold).
  Gegenwart = das Silber-Alarmfenster bis zur Replay-Uhr – das Ereignis ist noch offen,
              seine Gold-Zeile (Dauer, Ursache, Maßnahme) ist die verborgene Wahrheit.
Der Agent sieht nur Historie + Gegenwart. Der Vergleich Vorhersage ↔ Gold-Zeile ist die Eval.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

FMT = "%Y-%m-%d %H:%M:%S"


@dataclass
class ReplayCase:
    event_id: int
    line_id: str
    now: str  # Replay-Uhr: kurz nach Störungsbeginn
    truth: dict[str, Any] = field(default_factory=dict)  # Gold-Zeile, für den Agenten unsichtbar


def select_replay_cases(
    conn: sqlite3.Connection, n: int = 10, offset_min: int = 5, min_history: int = 20
) -> list[ReplayCase]:
    """Wählt die n jüngsten Gold-Ereignisse als Testfälle; davor müssen ≥ min_history
    abgeschlossene Ereignisse liegen, sonst gibt es keine Historie zum Lernen."""
    rows = conn.execute(
        "SELECT * FROM downtime_events_gold WHERE end_ts IS NOT NULL ORDER BY start_ts"
    ).fetchall()
    cases: list[ReplayCase] = []
    for r in rows[min_history:][-n:]:
        r = dict(r)
        now = datetime.fromisoformat(r["start_ts"]) + timedelta(minutes=offset_min)
        cases.append(
            ReplayCase(
                event_id=r["event_id"],
                line_id=r["line_id"],
                now=now.strftime(FMT),
                truth={
                    k: r[k]
                    for k in ("duration_min", "reason_code", "resolution_action", "cost_eur")
                },
            )
        )
    return cases


def case_for_event_id(
    conn: sqlite3.Connection, event_id: int, offset_min: int = 5
) -> ReplayCase | None:
    """Baut einen Replay-Fall für ein KONKRETES abgeschlossenes Gold-Ereignis (für --event-id).

    Die Replay-Uhr steht wie bei select_replay_cases kurz (offset_min) nach Störungsbeginn; die
    Gold-Zeile (Dauer, Ursache, Maßnahme, Kosten) ist die für den Agenten unsichtbare Wahrheit.
    Gibt None zurück, wenn das Ereignis nicht existiert oder noch nicht abgeschlossen ist.
    """
    row = conn.execute(
        "SELECT * FROM downtime_events_gold WHERE event_id = ? AND end_ts IS NOT NULL",
        (event_id,),
    ).fetchone()
    if row is None:
        return None
    r = dict(row)
    now = datetime.fromisoformat(r["start_ts"]) + timedelta(minutes=offset_min)
    return ReplayCase(
        event_id=r["event_id"],
        line_id=r["line_id"],
        now=now.strftime(FMT),
        truth={k: r[k] for k in ("duration_min", "reason_code", "resolution_action", "cost_eur")},
    )


def score(prediction: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    """Deterministische Bewertung einer Vorhersage gegen die Gold-Zeile."""
    reason_hit = prediction.get("reason_code") == truth.get("reason_code")
    pred_min = float(prediction.get("expected_downtime_min") or 0)
    abs_err = abs(pred_min - float(truth.get("duration_min") or 0))
    return {"reason_hit": reason_hit, "duration_abs_err_min": round(abs_err, 1)}


def latest_replay_ts(conn: sqlite3.Connection, offset_min: int = 5) -> str | None:
    """Replay-Uhr des jüngsten abgeschlossenen Ereignisses (Format: YYYY-MM-DD HH:MM:SS)."""
    row = conn.execute(
        "SELECT start_ts FROM downtime_events_gold WHERE end_ts IS NOT NULL "
        "ORDER BY start_ts DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    ts = datetime.fromisoformat(row[0]) + timedelta(minutes=offset_min)
    return ts.strftime(FMT)


if __name__ == "__main__":  # pragma: no cover
    import argparse
    import os
    import sys
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Replay-CLI")
    parser.add_argument("--latest", action="store_true", help="Replay-Uhr des jüngsten Falls")
    cli_args = parser.parse_args()

    if cli_args.latest:
        db_path = Path(os.getenv("DB_PATH", "data/gold/mes.sqlite"))
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        ts = latest_replay_ts(conn)
        if ts is not None:
            print(ts)
        else:
            print("Keine abgeschlossenen Ereignisse in der Datenbank.", file=sys.stderr)
            sys.exit(1)
