# Datenschicht Bronze→Silber→Gold

Technische Referenz für `src/production_agent/data/` (Simulator, Replay, Schema).

## Ebenen

### Bronze – Rohdaten

Datei: `data/bronze/alarms_raw.csv`  
Format (ALPI-Struktur): `machine, timestamp, alarm`  
Inhalt: Ein Alarm je Zeile, ohne Ereigniskontext, Priorität oder Aggregation.  
Quelle: Simulator (`export_bronze_csv`) oder echter ALPI-Export.

### Silber – angereicherte Alarmsequenzen

Tabelle: `alarms_silver`  
Aufbereitung:
- Priorität nach ISA-18.2 (Konsequenz × Reaktionszeit) oder OPC-UA-Severity-Band
- Alarmflut-Flag: >= 10 Alarme in 10 min innerhalb einer Sequenz (`alarm_flood = 1`)
- Sequenzierung: Alarme derselben Maschine mit Lücke <= 5 min bilden eine Sequenz (`sequence_id`)
- Bronze-Herkunft: `source_row_id = "sim:<event_id>:<alarm_id>"` (Simulator) oder `"csv:<machine>:<zeile>"` (build_from_bronze)

Funktion `build_from_bronze(csv_path, gap_min=5.0)` liest die Bronze-CSV und rekonstruiert
Silver-Zeilen für echte ALPI-Dateien.

### Gold – ein Eintrag je Störungsereignis

Tabelle: `downtime_events_gold`  
**Invariante: eine Zeile je Störungsereignis, nicht je Alarm** (ADR-0001).

Ereignisdefinition aus `decisions.yaml`:

| Kriterium | Wert |
|---|---|
| Beginn | PackML-Wechsel von Execute → Stopped/Held/Suspended/Aborted |
| Ende | Rückkehr nach Execute, mindestens 60 s stabil |
| Kurzstillstand | Dauer < 5 min ohne Prio-1-Alarm → `short_stops`, kein Gold-Eintrag |
| Prio-1-Alarm | immer Gold, unabhängig von der Dauer |

## Bronze→Silber→Gold für echte ALPI-Dateien

```python
from production_agent.data.simulator import build_from_bronze

rows = build_from_bronze("data/bronze/alarms_raw.csv")
# rows: Liste von Dicts mit machine, ts, alarm_code, sequence_id, alarm_flood, source_row_id
```

## Drei Kennzahlen (Gold-Tabelle)

| Kennzahl | Spalte | Norm |
|---|---|---|
| Stillstandsdauer je Ereignis | `duration_min` | ISO 22400-2 ADOT (unit down time) |
| Ausfallkosten je Ereignis | `cost_eur` | `duration_min × 200 €/min` (Linienkostensatz) |
| Alarmflut-Anteil | `alarm_flood = 1` ÷ Gesamtereignisse | ISA-18.2 / EEMUA 191 |

## Replay-Mechanismus

`replay.py` setzt eine Uhr (`SIM_NOW`) kurz nach dem Beginn eines Gold-Ereignisses:
- **Historie** = alle Gold-Ereignisse mit `end_ts <= SIM_NOW` (bekannte Lösung)
- **Gegenwart** = Silver-Alarme bis `SIM_NOW` (Ereignis läuft, Lösung unsichtbar)

Die Gold-Zeile des laufenden Ereignisses ist die verborgene Wahrheit für die Eval (ADR-0002).
