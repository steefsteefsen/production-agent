"""Deterministischer MES-Simulator – Entscheidungsbasis für den Production Agent.

Prinzip: EIN Generator erzeugt die gesamte Historie (Alarme, Zustände, Aufträge, Auflösungen),
die durch Bronze → Silber → Gold läuft. „Jetzt" ist ein Cursor auf einem Gold-Ereignis (replay.py):
alles davor ist Historie mit bekannter Lösung, das Ereignis selbst läuft „live" ohne Ende und ohne
Auflösung. Historie und aktueller Fall stammen also aus derselben Verteilung – wie im echten MES –
und die Lösung des aktuellen Falls ist für den Agenten unsichtbar (kein Leakage).
"""

from __future__ import annotations

import csv
import io
import random
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

PACKML_STOP_STATES = ["Stopped", "Held", "Suspended", "Aborted"]

# Alarmcode-Katalog je Störungsgrund:
# Erstalarm, typische Folgealarme, Ursache, Maßnahme, Dauer-Spanne, PackML-Zustand, Station
CATALOG: dict[str, dict[str, Any]] = {
    "STO-FOLIE": {
        "first": "E-4711",
        "follow": ["E-4713", "E-4720", "W-2101"],
        "cause": "Folienrolle falsch eingespannt / Folienriss",
        "action": "Folie neu einfädeln, Rolle prüfen, Station quittieren",
        "dur": (8, 25),
        "state": "Held",
        "station": 1,
    },
    "STO-SENSOR": {
        "first": "E-3302",
        "follow": ["E-3305", "W-2101"],
        "cause": "Lichttaster verschmutzt",
        "action": "Sensor reinigen, Lehre prüfen",
        "dur": (5, 20),
        "state": "Suspended",
        "station": 2,
    },
    "STO-ANTRIEB": {
        "first": "E-5101",
        "follow": ["E-5102", "E-5109", "E-4720", "W-2101"],
        "cause": "Antrieb Überstrom / Lager",
        "action": "Antrieb prüfen, ggf. Motor tauschen",
        "dur": (30, 120),
        "state": "Stopped",
        "station": 3,
    },
    "STO-ELEK": {
        "first": "E-6001",
        "follow": ["E-6002", "E-6003", "E-4720"],
        "cause": "Sicherung / Steuerung",
        "action": "Sicherung prüfen, Steuerung neu starten",
        "dur": (15, 60),
        "state": "Aborted",
        "station": 4,
    },
    "MAT-LEER": {
        "first": "W-1001",
        "follow": ["W-1002"],
        "cause": "Zuführung leer",
        "action": "Material nachfüllen",
        "dur": (3, 12),
        "state": "Suspended",
        "station": 0,
    },
    "MAT-STAU": {
        "first": "W-1201",
        "follow": ["W-1202", "E-4720"],
        "cause": "Produktstau Kartonierer",
        "action": "Stau beseitigen, Bandgeschwindigkeit prüfen",
        "dur": (4, 15),
        "state": "Held",
        "station": 4,
    },
    "SETUP": {
        "first": "I-0100",
        "follow": [],
        "cause": "Formatwechsel",
        "action": "Rüstvorgang abschließen",
        "dur": (25, 45),
        "state": "Stopped",
        "station": 2,
    },
    "QUAL-HOLD": {
        "first": "E-7001",
        "follow": ["E-7002"],
        "cause": "Siegelnaht außerhalb Toleranz",
        "action": "Temperatur nachregeln, Muster prüfen",
        "dur": (10, 30),
        "state": "Held",
        "station": 3,
    },
    "EXT-UP": {
        "first": "W-9001",
        "follow": [],
        "cause": "Vorgelagerte Anlage steht",
        "action": "Warten, Rückmeldung Vorlinie",
        "dur": (10, 40),
        "state": "Suspended",
        "station": 0,
    },
    "ORG": {
        "first": "I-0200",
        "follow": [],
        "cause": "Bedienerpause / Personal",
        "action": "Schichtplan",
        "dur": (5, 15),
        "state": "Held",
        "station": 5,
    },
}
WEIGHTS = {
    "STO-FOLIE": 30,
    "STO-SENSOR": 18,
    "STO-ANTRIEB": 6,
    "STO-ELEK": 6,
    "MAT-LEER": 12,
    "MAT-STAU": 10,
    "SETUP": 8,
    "QUAL-HOLD": 5,
    "EXT-UP": 3,
    "ORG": 2,
}
PRIORITY = {
    "E-4711": 2,
    "E-3302": 2,
    "E-5101": 1,
    "E-6001": 1,
    "E-7001": 2,
    "E-4720": 3,
    "W-2101": 3,
    "E-4713": 3,
    "E-3305": 3,
    "E-5102": 2,
    "E-5109": 3,
    "E-6002": 2,
    "E-6003": 3,
    "E-7002": 3,
    "W-1001": 3,
    "W-1002": 4,
    "W-1201": 3,
    "W-1202": 4,
    "W-9001": 3,
    "I-0100": 4,
    "I-0200": 4,
}


@dataclass
class Event:
    event_id: int
    reason: str
    start: datetime
    end: datetime
    station: int
    alarms: list[tuple[datetime, str, int]]  # ts, code, priority
    flood: bool
    ai4i: dict[str, float]


def load_decisions(path: str | Path = "decisions.yaml") -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _ai4i_snapshot(rng: random.Random, reason: str) -> dict[str, float]:
    """Sensor-Snapshot im AI4I-Wertebereich; bei Antrieb/Elektrik triggern die Regeln bewusst."""
    typ = rng.choice("LLLLLLMMMH")
    air = rng.gauss(300, 2)
    proc = air + rng.gauss(10, 1)
    rpm = rng.gauss(1540, 180)
    torque = max(3.0, rng.gauss(40, 10))
    wear = rng.uniform(0, 200)
    if reason == "STO-ANTRIEB":
        torque, wear = rng.uniform(55, 75), rng.uniform(205, 240)  # OSF/TWF
    if reason == "STO-ELEK":
        rpm, torque = rng.uniform(2400, 2800), rng.uniform(45, 70)  # PWF > 9000 W
    return {
        "type": typ,
        "air_temp": round(air, 1),
        "process_temp": round(proc, 1),
        "rpm": round(rpm),
        "torque": round(torque, 1),
        "tool_wear": round(wear),
    }


def generate(dec: dict[str, Any]) -> list[Event]:
    sim, ev_def = dec["simulation"], dec["ereignis"]
    rng = random.Random(sim["seed"])  # noqa: S311  # nosec B311 – Simulation, keine Kryptografie
    t = datetime(2026, 6, 1, 6, 0)
    events: list[Event] = []
    n = int(sim["tage_historie"] * sim["ereignisse_pro_tag"])
    reasons = list(WEIGHTS)
    for i in range(n):
        t += timedelta(minutes=rng.expovariate(1 / (24 * 60 / sim["ereignisse_pro_tag"])))
        reason = rng.choices(reasons, weights=[WEIGHTS[r] for r in reasons])[0]
        c = CATALOG[reason]
        dur = rng.uniform(*c["dur"])
        alarms = [(t, c["first"], PRIORITY[c["first"]])]
        # Folgealarme: bei Störungen oft Kaskade → Alarmflut nach ISA-18.2
        n_follow = rng.randint(0, 3) if not reason.startswith("STO") else rng.randint(4, 40)
        for _ in range(n_follow):
            code = rng.choice(c["follow"] or [c["first"]])
            alarms.append(
                (t + timedelta(minutes=rng.uniform(0, min(dur, 12))), code, PRIORITY[code])
            )
        alarms.sort()
        flood = _is_flood(alarms, ev_def["alarmflut_alarme"], ev_def["alarmflut_fenster_min"])
        events.append(
            Event(
                i + 1,
                reason,
                t,
                t + timedelta(minutes=dur),
                c["station"],
                alarms,
                flood,
                _ai4i_snapshot(rng, reason),
            )
        )
    # Demo-Ereignis erzwingen (Zustand und Erstalarm aus decisions.yaml)
    demo = events[-1 - sim["demo_ereignis_index_von_hinten"]]
    reason = next(r for r, c in CATALOG.items() if c["first"] == sim["demo_alarm_code"])
    c = CATALOG[reason]
    demo.reason, demo.station = reason, c["station"]
    demo.alarms = [
        (demo.start + timedelta(seconds=s * 20), code, PRIORITY[code])
        for s, code in enumerate([c["first"]] + [rng.choice(c["follow"]) for _ in range(36)])
    ]
    demo.flood = True
    return events


def _is_flood(alarms: list[tuple[datetime, str, int]], n: int, window: int) -> bool:
    ts = [a[0] for a in alarms]
    for i in range(len(ts)):
        if sum(1 for x in ts if timedelta(0) <= x - ts[i] <= timedelta(minutes=window)) >= n:
            return True
    return False


def write_sqlite(
    dec: dict[str, Any],
    events: list[Event],
    db_path: str | Path,
    schema_path: str | Path = "src/production_agent/data/schema.sql",
) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.executescript(Path(schema_path).read_text(encoding="utf-8"))
    line = dec["linie"]
    conn.execute(
        "INSERT INTO lines VALUES (?,?,?,?,?)",
        (
            line["line_id"],
            line["name"],
            line["plant"],
            line["design_rate_per_hour"],
            line["cost_per_downtime_minute_eur"],
        ),
    )
    for i, st in enumerate(line["stationen"]):
        conn.execute(
            "INSERT INTO equipment VALUES (?,?,?,?)",
            (f"{line['line_id']}-S{i}", line["line_id"], st, i),
        )
    for code, cat, desc, loss in dec["reason_codes"]:
        conn.execute("INSERT INTO downtime_reason_codes VALUES (?,?,?,?)", (code, cat, desc, loss))
    alarm_id = 0
    for ev in events:
        eq = f"{line['line_id']}-S{ev.station}"
        c = CATALOG[ev.reason]
        dur = (ev.end - ev.start).total_seconds() / 60
        lost = round(line["design_rate_per_hour"] * dur / 60)
        cost = round(line["cost_per_downtime_minute_eur"] * dur, 2)
        for ts, code, prio in ev.alarms:
            alarm_id += 1
            conn.execute(
                "INSERT INTO alarms_silver VALUES (?,?,?,?,?,?,?)",
                (
                    alarm_id,
                    eq,
                    ts.replace(microsecond=0).isoformat(sep=" "),
                    code,
                    prio,
                    ev.event_id,
                    f"sim:{ev.event_id}:{alarm_id}",
                ),
            )
        conn.execute(
            "INSERT INTO equipment_state VALUES (?,?,?)",
            (eq, ev.start.replace(microsecond=0).isoformat(sep=" "), c["state"]),
        )
        conn.execute(
            "INSERT INTO equipment_state VALUES (?,?,?)",
            (eq, ev.end.replace(microsecond=0).isoformat(sep=" "), "Execute"),
        )
        conn.execute(
            "INSERT INTO downtime_events_gold VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                ev.event_id,
                line["line_id"],
                eq,
                ev.start.replace(microsecond=0).isoformat(sep=" "),
                ev.end.replace(microsecond=0).isoformat(sep=" "),
                round(dur, 1),
                c["state"],
                ev.reason,
                ev.alarms[0][1],
                len(ev.alarms),
                int(ev.flood),
                None,
                lost,
                cost,
                c["action"],
            ),
        )
        conn.execute(
            "INSERT INTO incident_history VALUES (?,?,?,?,?,?,?)",
            (
                ev.event_id,
                ev.event_id,
                f"{c['state']} an {line['stationen'][ev.station]} nach {ev.alarms[0][1]}",
                c["cause"],
                c["action"],
                f"Wiederanlauf nach {dur:.0f} min",
                f"Wartung_{line['stationen'][ev.station]}.md",
            ),
        )
        conn.execute(
            "INSERT OR REPLACE INTO ai4i_snapshots VALUES (?,?,?,?,?,?,?)",
            (
                ev.event_id,
                ev.ai4i["type"],
                ev.ai4i["air_temp"],
                ev.ai4i["process_temp"],
                ev.ai4i["rpm"],
                ev.ai4i["torque"],
                ev.ai4i["tool_wear"],
            ),
        )
    # Aufträge rund um das Demo-Ereignis
    demo = events[-1 - dec["simulation"]["demo_ereignis_index_von_hinten"]]
    conn.execute(
        "INSERT INTO production_orders VALUES (?,?,?,?,?,?,?)",
        (
            "A-2207",
            line["line_id"],
            "Karton 12er",
            4800,
            3120,
            (demo.start + timedelta(minutes=40)).isoformat(sep=" "),
            1,
        ),
    )
    conn.execute(
        "INSERT INTO production_orders VALUES (?,?,?,?,?,?,?)",
        (
            "A-2208",
            line["line_id"],
            "Karton 6er",
            2400,
            0,
            (demo.start + timedelta(hours=8)).isoformat(sep=" "),
            3,
        ),
    )
    conn.commit()
    conn.close()


def export_bronze_csv(events: list[Event]) -> str:
    """Rohform (Bronze) als CSV-Text – dieselbe Struktur wie ALPI: machine, timestamp, alarm."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["machine", "timestamp", "alarm"])
    for ev in events:
        for ts, code, _ in ev.alarms:
            w.writerow([f"S{ev.station}", ts.isoformat(), code])
    return buf.getvalue()


if __name__ == "__main__":
    dec = load_decisions()
    evs = generate(dec)
    Path("data/bronze/alarms_raw.csv").write_text(export_bronze_csv(evs), encoding="utf-8")
    write_sqlite(dec, evs, "data/gold/mes.sqlite")
    avg = sum((e.end - e.start).total_seconds() / 60 for e in evs) / len(evs)
    flood_share = sum(e.flood for e in evs) / len(evs)
    print(f"{len(evs)} Ereignisse, Ø {avg:.1f} min, Alarmflut-Anteil {flood_share:.0%}")
