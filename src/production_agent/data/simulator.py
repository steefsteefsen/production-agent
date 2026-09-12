"""Deterministischer MES-Simulator – Entscheidungsbasis für den Production Agent.

Prinzip: EIN Generator erzeugt die gesamte Historie (Alarme, Zustände, Aufträge, Auflösungen),
die durch Bronze → Silber → Gold läuft. „Jetzt" ist ein Cursor auf einem Gold-Ereignis (replay.py):
alles davor ist Historie mit bekannter Lösung, das Ereignis selbst läuft „live" ohne Ende und ohne
Auflösung. Historie und aktueller Fall stammen also aus derselben Verteilung – wie im echten MES –
und die Lösung des aktuellen Falls ist für den Agenten unsichtbar (kein Leakage).

Regeln aus decisions.yaml (ADR-0001): Beginn = PackML-Wechsel weg von Execute, Erstalarm im Fenster
±erstalarm_fenster_s, Ereignisende = Execute ≥ 60 s stabil, Ereignisse < kurzstillstand_min ohne
Prio-1-Alarm sind Kurzstillstände (Tabelle short_stops, nicht Gold), Prio-1 ist immer Gold.
Alarmpriorität nach alarm_prioritaet.verfahren (isa18_matrix Standard oder hersteller_severity),
Severity 1–1000 je Alarm mitgeführt. Vorgelagerte Anlage UP1 sendet StateChange (Grund EXT-UP).
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

# Alarmcode-Katalog je Störungsgrund (deckt alle 14 reason_codes aus decisions.yaml):
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
    "STO-SIEGEL": {
        "first": "E-7101",
        "follow": ["E-7102", "E-4720"],
        "cause": "Siegeltemperatur außerhalb Toleranz / Heizung",
        "action": "Heizung prüfen, Temperatur nachregeln, Station quittieren",
        "dur": (10, 35),
        "state": "Held",
        "station": 3,
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
    "MAT-KARTON": {
        "first": "W-6401",
        "follow": ["W-6402"],
        "cause": "Kartonvorrat leer",
        "action": "Kartons nachlegen, Magazin prüfen",
        "dur": (5, 14),
        "state": "Suspended",
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
    "QUAL-NIO": {
        "first": "E-7201",
        "follow": ["E-7202"],
        "cause": "Ausschussrate über Grenze",
        "action": "Prozess prüfen, Muster ziehen, Charge sperren",
        "dur": (8, 25),
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
    "EXT-DOWN": {
        "first": "W-9101",
        "follow": [],
        "cause": "Nachgelagerte Anlage / Abtransport steht",
        "action": "Abtransport klären, Puffer prüfen",
        "dur": (8, 30),
        "state": "Suspended",
        "station": 5,
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
    "STO-FOLIE": 24,
    "STO-SENSOR": 14,
    "STO-ANTRIEB": 5,
    "STO-ELEK": 5,
    "STO-SIEGEL": 5,
    "MAT-LEER": 8,
    "MAT-STAU": 7,
    "MAT-KARTON": 4,
    "SETUP": 6,
    "QUAL-HOLD": 4,
    "QUAL-NIO": 3,
    "EXT-UP": 8,
    "EXT-DOWN": 3,
    "ORG": 4,
}
# ISA-18.2-Matrix-Priorität je Alarmcode (Konsequenz × Reaktionszeit)
PRIORITY = {
    "E-4711": 2,
    "E-3302": 2,
    "E-5101": 1,
    "E-6001": 1,
    "E-7001": 2,
    "E-7101": 2,
    "E-7201": 3,
    "E-4720": 3,
    "W-2101": 3,
    "E-4713": 3,
    "E-3305": 3,
    "E-5102": 2,
    "E-5109": 3,
    "E-6002": 2,
    "E-6003": 3,
    "E-7002": 3,
    "E-7102": 3,
    "E-7202": 3,
    "W-1001": 3,
    "W-1002": 4,
    "W-1201": 3,
    "W-1202": 4,
    "W-6401": 4,
    "W-6402": 4,
    "W-9001": 3,
    "W-9101": 3,
    "I-0100": 4,
    "I-0200": 4,
}
# Severity-Basis je ISA-Priorität (OPC-UA-Band-Mitte) für das Verfahren hersteller_severity
_SEV_BASE = {1: 850, 2: 680, 3: 480, 4: 280}


@dataclass
class Event:
    event_id: int
    reason: str
    start: datetime
    end: datetime
    station: int
    alarms: list[tuple[datetime, str, int, int]]  # ts, code, priority, severity
    flood: bool
    ai4i: dict[str, float]


def load_decisions(path: str | Path = "decisions.yaml") -> dict[str, Any]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _severity(rng: random.Random, code: str) -> int:
    return max(1, min(1000, round(rng.gauss(_SEV_BASE[PRIORITY[code]], 110))))


def _band(sev: int) -> int:
    return 1 if sev >= 800 else 2 if sev >= 600 else 3 if sev >= 400 else 4


def _prio(code: str, sev: int, verfahren: str) -> int:
    """Priorität nach gewähltem Verfahren: ISA-18.2-Matrix (fest) oder Hersteller-Severity-Band."""
    return PRIORITY[code] if verfahren == "isa18_matrix" else _band(sev)


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
    verfahren = dec["alarm_prioritaet"]["verfahren"]
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
        sev0 = _severity(rng, c["first"])
        alarms = [(t, c["first"], _prio(c["first"], sev0, verfahren), sev0)]
        # Folgealarme: bei Störungen oft Kaskade → Alarmflut nach ISA-18.2
        n_follow = rng.randint(0, 3) if not reason.startswith("STO") else rng.randint(4, 40)
        for _ in range(n_follow):
            code = rng.choice(c["follow"] or [c["first"]])
            sev = _severity(rng, code)
            ts = t + timedelta(minutes=rng.uniform(0, min(dur, 12)))
            alarms.append((ts, code, _prio(code, sev, verfahren), sev))
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
    # Demo-Ereignis erzwingen (Zustand, Erstalarm, Dauer aus decisions.yaml → Gold mit Alarmflut)
    demo = events[-1 - sim["demo_ereignis_index_von_hinten"]]
    reason = next(r for r, c in CATALOG.items() if c["first"] == sim["demo_alarm_code"])
    c = CATALOG[reason]
    demo.reason, demo.station = reason, c["station"]
    demo.alarms = []
    for s, code in enumerate([c["first"]] + [rng.choice(c["follow"]) for _ in range(36)]):
        sev = _severity(rng, code)
        ts = demo.start + timedelta(seconds=s * 20)
        demo.alarms.append((ts, code, _prio(code, sev, verfahren), sev))
    demo.flood = True
    demo.end = demo.start + timedelta(minutes=rng.uniform(*c["dur"]))
    return events


def _is_flood(alarms: list[tuple[datetime, str, int, int]], n: int, window: int) -> bool:
    ts = [a[0] for a in alarms]
    for i in range(len(ts)):
        if sum(1 for x in ts if timedelta(0) <= x - ts[i] <= timedelta(minutes=window)) >= n:
            return True
    return False


def _event_prio(ev: Event) -> int:
    """Dringlichkeit des Ereignisses = kleinste (dringendste) Alarmpriorität; 4 ohne Alarm."""
    return min((a[2] for a in ev.alarms), default=4)


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
    kurz = dec["ereignis"]["kurzstillstand_min"]
    prio1_immer = dec["ereignis"]["prio1_immer_ereignis"]
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
    # Vorgelagerte Anlage UP1 als externe Quelle (sendet nur StateChange)
    up = line.get("vorgelagerte_anlage")
    if up:
        conn.execute(
            "INSERT INTO equipment VALUES (?,?,?,?)",
            (up["id"], line["line_id"], up["name"], len(line["stationen"])),
        )
    for code, cat, desc, loss in dec["reason_codes"]:
        conn.execute("INSERT INTO downtime_reason_codes VALUES (?,?,?,?)", (code, cat, desc, loss))
    alarm_id = 0
    for ev in events:
        eq = f"{line['line_id']}-S{ev.station}"
        c = CATALOG[ev.reason]
        dur = (ev.end - ev.start).total_seconds() / 60
        start_iso = ev.start.replace(microsecond=0).isoformat(sep=" ")
        end_iso = ev.end.replace(microsecond=0).isoformat(sep=" ")
        ev_prio = _event_prio(ev)
        to_gold = (prio1_immer and ev_prio == 1) or dur >= kurz
        if not to_gold:
            # Kurzstillstand (Leistungsverlust) – nicht in Gold, aggregiert in short_stops
            conn.execute(
                "INSERT INTO short_stops VALUES (?,?,?,?)",
                (line["stationen"][ev.station], start_iso, end_iso, round(dur, 1)),
            )
            continue
        for ts, code, prio, sev in ev.alarms:
            alarm_id += 1
            conn.execute(
                "INSERT INTO alarms_silver VALUES (?,?,?,?,?,?,?,?)",
                (
                    alarm_id,
                    eq,
                    ts.replace(microsecond=0).isoformat(sep=" "),
                    code,
                    prio,
                    sev,
                    ev.event_id,
                    f"sim:{ev.event_id}:{alarm_id}",
                ),
            )
        conn.execute("INSERT INTO equipment_state VALUES (?,?,?)", (eq, start_iso, c["state"]))
        conn.execute("INSERT INTO equipment_state VALUES (?,?,?)", (eq, end_iso, "Execute"))
        if ev.reason == "EXT-UP" and up:  # UP1 sendet StateChange, Ursache außerhalb der Linie
            uid = up["id"]
            sql_state = "INSERT OR IGNORE INTO equipment_state VALUES (?,?,?)"
            conn.execute(sql_state, (uid, start_iso, "Stopped"))
            conn.execute(sql_state, (uid, end_iso, "Execute"))
        lost = round(line["design_rate_per_hour"] * dur / 60)
        cost = round(line["cost_per_downtime_minute_eur"] * dur, 2)
        conn.execute(
            "INSERT INTO downtime_events_gold VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                ev.event_id,
                line["line_id"],
                eq,
                start_iso,
                end_iso,
                round(dur, 1),
                c["state"],
                ev.reason,
                ev.alarms[0][1],
                ev_prio,
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
        for ts, code, _, _ in ev.alarms:
            w.writerow([f"S{ev.station}", ts.isoformat(), code])
    return buf.getvalue()


def _flush_sequence(
    entries: list[tuple[datetime, str, int]],
    machine: str,
    seq_id: int,
    flood_n: int,
    flood_win: int,
    out: list[dict[str, Any]],
) -> None:
    """Schreibt eine abgeschlossene Alarmsequenz als Silver-Zeilen in out."""
    flood = int(_is_flood([(ts, "", 0, 0) for ts, _, _ in entries], flood_n, flood_win))
    for ts, alarm, row_num in entries:
        out.append(
            {
                "machine": machine,
                "ts": ts.replace(microsecond=0).isoformat(sep=" "),
                "alarm_code": alarm,
                "sequence_id": seq_id,
                "alarm_flood": flood,
                "source_row_id": f"csv:{machine}:{row_num}",
            }
        )


def build_from_bronze(
    csv_path: str | Path,
    gap_min: float = 5.0,
    flood_n: int = 10,
    flood_win: int = 10,
) -> list[dict[str, Any]]:
    """Liest Bronze-CSV (machine,timestamp,alarm) und rekonstruiert Silver-Zeilen.

    Sequenzierung: aufeinanderfolgende Alarme derselben Maschine mit Lücke <= gap_min
    bilden eine Sequenz (sequence_id). Alarmflut-Flag: >= flood_n Alarme in flood_win min.
    source_row_id: 'csv:{machine}:{zeilennummer}' sichert Bronze→Silber-Rückverfolgbarkeit.
    """
    rows_by_machine: dict[str, list[tuple[datetime, str, int]]] = {}
    with Path(csv_path).open(encoding="utf-8", newline="") as f:
        for row_num, row in enumerate(csv.DictReader(f), start=2):
            ts = datetime.fromisoformat(row["timestamp"])
            rows_by_machine.setdefault(row["machine"], []).append((ts, row["alarm"], row_num))

    silver: list[dict[str, Any]] = []
    seq_id = 0
    gap = timedelta(minutes=gap_min)

    for machine, entries in rows_by_machine.items():
        entries.sort()
        current: list[tuple[datetime, str, int]] = []
        for ts, alarm, row_num in entries:
            if current and ts - current[-1][0] > gap:
                seq_id += 1
                _flush_sequence(current, machine, seq_id, flood_n, flood_win, silver)
                current = []
            current.append((ts, alarm, row_num))
        if current:
            seq_id += 1
            _flush_sequence(current, machine, seq_id, flood_n, flood_win, silver)

    return silver


if __name__ == "__main__":
    import argparse
    import json
    import sys
    import time as _time

    ap = argparse.ArgumentParser(description="MES-Simulator")
    ap.add_argument("--stream", action="store_true", help="Demo-Ereignis als JSON-Zeilen streamen")
    ap.add_argument(
        "--speed",
        type=float,
        default=60.0,
        metavar="N",
        help="Zeitrafferrate: 1 Echtzeit-Sekunde = N Sim-Sekunden (Standard 60)",
    )
    args = ap.parse_args()

    dec = load_decisions()
    evs = generate(dec)

    if args.stream:
        demo = evs[-1 - dec["simulation"]["demo_ereignis_index_von_hinten"]]
        verfahren = dec["alarm_prioritaet"]["verfahren"]
        stationen = dec["linie"]["stationen"]
        line_id = dec["linie"]["line_id"]
        station_name = (
            stationen[demo.station] if demo.station < len(stationen) else f"S{demo.station}"
        )
        if not demo.alarms:
            sys.exit(0)
        ref_ts = demo.alarms[0][0]
        for ts, code, prio, sev in demo.alarms:
            delay = max(0.0, (ts - ref_ts).total_seconds() / args.speed)
            if delay > 0:
                _time.sleep(delay)
            ref_ts = ts
            payload = {
                "source_node": f"{line_id}-S{demo.station}/{station_name}",
                "alarm_id": f"{code}/{ts.isoformat()}",
                "alarm_code": code,
                "severity": sev,
                "priority": prio,
                "message": CATALOG[demo.reason]["cause"],
                "active": True,
                "ts": ts.isoformat(),
                "topic": f"plant/{line_id}/{station_name}/alarm",
            }
            print(json.dumps(payload, ensure_ascii=False), flush=True)
    else:
        Path("data/bronze/alarms_raw.csv").write_text(export_bronze_csv(evs), encoding="utf-8")
        write_sqlite(dec, evs, "data/gold/mes.sqlite")
        kurz = dec["ereignis"]["kurzstillstand_min"]
        gold = [
            e
            for e in evs
            if (dec["ereignis"]["prio1_immer_ereignis"] and _event_prio(e) == 1)
            or (e.end - e.start).total_seconds() / 60 >= kurz
        ]
        avg = sum((e.end - e.start).total_seconds() / 60 for e in gold) / len(gold)
        flood_share = sum(e.flood for e in gold) / len(gold)
        print(
            f"{len(gold)} Ereignisse (+{len(evs) - len(gold)} Kurzstillstände), "
            f"Ø {avg:.1f} min, Alarmflut-Anteil {flood_share:.0%}"
        )
