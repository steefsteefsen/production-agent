# ADR-0010: MES-Nachrichtenformat – OPC UA A&C + ISA-95 JSON

Datum: 2026-09-12 · Status: akzeptiert

## Kontext
Der Production Agent empfängt Alarme, Zustandswechsel und Auftragsfortschritte von der Verpackungslinie.
Das Nachrichtenformat legt fest, welche Felder jede Meldung trägt, wie Topics strukturiert sind und
nach welchem Verfahren die Severity auf ISA-18.2-Prioritäten gemappt wird.
Die Wahl beeinflusst, welche Normenbezüge der Agent in Empfehlungen nennen kann und ob die Anbindung
an ein reales MES/SCADA nachvollziehbar bleibt.

## Optionen

| Option | Format | Normbezug | Priorität | Aufwand | Risiko |
|---|---|---|---|---|---|
| **A (gewählt)** | OPC UA Alarms & Conditions + ISA-95 als JSON-Event | IEC 62541 OPC UA, ISA-95 / IEC 62264 | Severity-Band ≥800→1, 600–799→2, 400–599→3, <400→4 (OPC-UA-native); alternativ ISA-18.2-Matrix | ●● – Pydantic-Mapping, kein OPC-UA-Stack | ●●● niedrig; bestehende ISA-18.2-Matrix weiter nutzbar |
| B | Sparkplug B (MQTT) | Eclipse Sparkplug B 3.0 | Herstellerkodierung, kein Standard | ●● | ● – kein MQTT-Broker in der PoC-Architektur |
| C | Proprietäres CSV (wie Bronze-Layer) | keiner | keine native Priorität | ●●● einfach | ● – kein Normbezug; Silver-Ebene verliert Traceability |

## Entscheidung
Option A. Drei Pydantic-Modelle für die drei ISA-95-Ereignistypen:

| Modell | ISA-95-Entität | OPC-UA-Quelle |
|---|---|---|
| `AlarmEvent` | AlarmEvent (A&C NodeClass) | OPC UA Server A&C-Interface |
| `StateChange` | PackML-Zustandswechsel | OPC UA State Machine |
| `OrderProgress` | WorkRequest / JobOrder | MES-ISA-95-Interface |

**Topic-Schema:** `plant/<line_id>/<station>/<alarm|state|order>`
Beispiel: `plant/L1/Folienwickler/alarm`

**Severity → Priorität:**
```
≥ 800  → ISA-18.2-Prio 1 (Sicherheit / Anlagenschaden)
600–799 → Prio 2 (dringend)
400–599 → Prio 3 (normal)
< 400  → Prio 4 (Hinweis/Info)
```
Das Verfahren entspricht den OPC-UA-Severity-Bändern (IEC 62541-9) und ist zu ISA-18.2 kompatibel.
Alternativverfahren `isa18_matrix` bleibt Simulator-Standard; der PoC unterstützt beide (`decisions.yaml alarm_prioritaet.verfahren`).

**Pflichtfeld `source_node`:** Identifiziert die OPC-UA-NodeId der meldenden Quelle.
Fehlendes `source_node` → Pydantic-ValidationError / HTTP 422 (Traceability-Pflicht, IEC 62443 §6.3).

## Konsequenzen / Kurzfassung für die Präsentation
„Ich verwende OPC-UA-Severity-Bänder, weil das der direkte Weg vom Controller-Attribut zur
ISA-18.2-Priorität ist – ohne proprietäre Tabelle. Die source_node-Pflicht macht jede Meldung
rückverfolgbar, das ist IEC 62443-Forderung für OT-Systeme."

Kosten: kein echter OPC-UA-Stack, Simulator schreibt Format direkt; kein Mehraufwand in Bronze-Layer
(source_row_id bleibt Rückkanal). Sparkplug B wäre der Produktionsweg bei MQTT-Infrastruktur.

## Quellen (mit Datum)

- IEC 62541-9:2022 (OPC UA – Alarms and Conditions), Severity-Bänder §8.3
- ANSI/ISA-18.2-2016, Alarm Management: Prioritätsstufen 1–4, Alarmflut ≥10 in 10 min
- ISA-95 / IEC 62264-2:2013, Manufacturing Operations Management: WorkRequest, JobOrder
- Eclipse Sparkplug Specification 3.0.0, 2023 – abgelehnt: kein MQTT-Broker im PoC-Stack
- OPC Foundation, „OPC UA Part 14: PubSub" 1.05.03, 2022 – Topic-Konvention übernommen
- IEC 62443-3-3:2013, SR 6.2: Rückverfolgbarkeit aller Steuerbefehle (source_node-Pflicht)
- Lemcon, „OEE-Verfügbarkeit automatisch messen", 2026-03-05 – Praxisreferenz CSV → Silver
