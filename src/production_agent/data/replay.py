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


def score(prediction: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    """Deterministische Bewertung einer Vorhersage gegen die Gold-Zeile."""
    reason_hit = prediction.get("reason_code") == truth.get("reason_code")
    pred_min = float(prediction.get("expected_downtime_min") or 0)
    abs_err = abs(pred_min - float(truth.get("duration_min") or 0))
    return {"reason_hit": reason_hit, "duration_abs_err_min": round(abs_err, 1)}
