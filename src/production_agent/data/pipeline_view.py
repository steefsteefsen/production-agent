"""Bronze → Silber → Gold Herkunftskette mit Regel-Chips.

Verwendung CLI:
    python -m production_agent.data.pipeline_view --event 1 --db data/gold/mes.sqlite
"""

from __future__ import annotations

from typing import Any

from production_agent.security.sql_guard import open_readonly, run_readonly


def get_lineage(event_id: int, db_path: str) -> dict[str, Any] | None:
    """Vollständige Herkunftskette eines Gold-Ereignisses.

    Rückgabe:
        event_id, reason_code, packml_state, start_ts, end_ts, duration_min,
        first_alarm_code, alarm_count, bronze_ids (Liste source_row_id),
        silver_alarms (Detailzeilen), rules_applied (Regel-Chips als Text).
    Gibt None zurück, wenn das Ereignis nicht gefunden wurde.
    """
    conn = open_readonly(db_path)
    try:
        gold = run_readonly(
            conn,
            "SELECT event_id, reason_code, packml_state, start_ts, end_ts, duration_min, "
            "first_alarm_code, first_alarm_prio, alarm_count, alarm_flood "
            "FROM downtime_events_gold WHERE event_id = ?",
            (event_id,),
            max_rows=1,
        )
        if not gold:
            return None
        g = gold[0]

        silver = run_readonly(
            conn,
            "SELECT alarm_id, equipment_id, ts, alarm_code, priority, severity, "
            "sequence_id, source_row_id "
            "FROM alarms_silver WHERE sequence_id = ? ORDER BY ts",
            (event_id,),
            max_rows=200,
        )
    finally:
        conn.close()

    bronze_ids = [r["source_row_id"] for r in silver if r.get("source_row_id")]

    rules: list[str] = [
        f"Sequenzierung: {len(silver)} Alarm(e) in einer Sequenz (Gap ≤ 5 min, ISA-18.2)",
    ]
    if g.get("alarm_flood"):
        rules.append("Alarmflut: ≥ 10 Alarme in 10 min (ISA-18.2 / EEMUA 191)")
    if g.get("first_alarm_prio") == 1:
        rules.append("Prio-1-Alarm: Sicherheits-/Anlagenschaden → immer Ereignis (ADR-0001)")
    dur = g.get("duration_min")
    if dur is not None:
        if dur >= 5:
            rules.append(f"Verfügbarkeitsverlust: {dur:.1f} min ≥ 5 min Schwelle (VDMA 66412)")
        else:
            rules.append(f"Kurzstillstand: {dur:.1f} min < 5 min (Leistungsverlust, ADET)")

    return {
        "event_id": g["event_id"],
        "reason_code": g.get("reason_code"),
        "packml_state": g.get("packml_state"),
        "start_ts": g.get("start_ts"),
        "end_ts": g.get("end_ts"),
        "duration_min": dur,
        "first_alarm_code": g.get("first_alarm_code"),
        "alarm_count": g.get("alarm_count"),
        "bronze_ids": bronze_ids,
        "silver_alarms": silver,
        "rules_applied": rules,
    }


def _print_lineage(event_id: int, db_path: str) -> None:
    lin = get_lineage(event_id, db_path)
    if lin is None:
        print(f"Ereignis {event_id} nicht gefunden in {db_path}")
        return

    print(f"\n=== Herkunftskette Ereignis {event_id} ===")
    print(
        f"Gold:   {lin['packml_state']} | {lin['reason_code']} | "
        f"{lin['start_ts']} → {lin['end_ts']} ({lin['duration_min']:.1f} min)"
    )
    print(f"        Erstalarm: {lin['first_alarm_code']} | Alarme: {lin['alarm_count']}")
    print()
    print("Silber-Regeln (Chips):")
    for rule in lin["rules_applied"]:
        print(f"  ✦ {rule}")
    print()
    print(f"Bronze-IDs ({len(lin['bronze_ids'])}):")
    for bid in lin["bronze_ids"][:10]:
        print(f"  • {bid}")
    if len(lin["bronze_ids"]) > 10:
        print(f"  … (+{len(lin['bronze_ids']) - 10} weitere)")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Bronze→Silber→Gold Herkunftskette")
    ap.add_argument("--event", type=int, default=1, help="Ereignis-ID")
    ap.add_argument("--db", default="data/gold/mes.sqlite", help="Pfad zur MES-SQLite-DB")
    args = ap.parse_args()

    _print_lineage(args.event, args.db)
