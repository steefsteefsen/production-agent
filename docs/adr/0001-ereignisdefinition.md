# ADR-0001: Störungsereignis – Beginn, Ende, Zusammenfassung

Datum: 2026-09-11 · Status: akzeptiert

## Kontext
Der Agent entscheidet je *Ereignis*, nicht je Alarm. Gold = eine Zeile je Störungsereignis. Damit das belastbar ist, muss
feststehen, wann ein Ereignis beginnt, endet, und wann zwei Stopps eines sind. VDMA 66412-1 und ISO 22400-2 schreiben keine
Schwelle vor, sondern verlangen, dass der Betrieb „Ausfall", „Kurzstillstand" und „geplanter Stillstand" selbst definiert und
konsequent anwendet; das Zeitmodell liefert die Elemente (ADOT unit down time, ADET delay time, APT production time).
PackML (ISA-TR88.00.02) liefert die Zustände, ISA-18.2 die Alarmflut-Definition.

## Optionen
| Option | Beginn | Ende | Kurzstillstand | Zusammenfassung | Bewertung |
|---|---|---|---|---|---|
| **A (gewählt)** | PackML-Wechsel weg von Execute nach Stopped/Held/Suspended/Aborted; erster Alarm ±60 s = Erstalarm | Execute ≥ 60 s stabil | < 5 min ohne Prio-1-Alarm → Leistungsverlust (ADET), kein Ereignis; jeder Prio-1-Alarm ist Ereignis | Lücke ≤ 5 min | Zustand ist Faktum, Alarm ist Evidenz; deckungsgleich mit OEE-Verlusttypen; Sicherheitsalarme nie verschluckt |
| B | Erster Alarm Prio 1–2 | Execute | keine Schwelle | Lücke ≤ 5 min | einfach, aber ein Alarm ohne Stopp erzeugt Ereignisse; ein Stopp ohne Alarm (Bediener) fehlt |
| C | Jeder PackML-Wechsel | Execute | keine | Lücke ≤ 10 min | vollständig, aber Kurzstillstände dominieren die Historie (häufig 60–70 %), Ähnlichkeitssuche wird unscharf |
| D | Wie A, Kurzstillstand < 10 min | Execute | < 10 min | Lücke ≤ 10 min | weniger, längere Ereignisse; verwässert Verpackungslinien-Praxis (5 min üblich) |

## Entscheidung
Option A. Jede Gold-Zeile trägt ADOT (duration_min), first_alarm_code, packml_state, reason_code mit OEE-Verlusttyp,
alarm_count, alarm_flood (≥ 10 in 10 min). Kurzstillstände werden je Schicht aggregiert und im OEE-Wasserfall als
Leistungsverlust gezeigt, nicht als Ereignis untersucht. Die Werte stehen in decisions.yaml (ereignis.*).

## Konsequenzen / Kurzfassung für die Präsentation
„Ich aggregiere Alarme zu Ereignissen, weil der Produktionsleiter Ereignisse entscheidet. Beginn ist der Zustandswechsel,
nicht der Alarm – der Alarm ist die Evidenz. Unter fünf Minuten ist es ein Kurzstillstand und Leistungsverlust, darüber ein
Verfügbarkeitsverlust; Sicherheitsalarme sind immer ein Ereignis. Das ist VDMA-66412-Logik, nicht meine Erfindung."
Kosten: der Simulator und die Silber-Ebene müssen Zustandswechsel und Alarme getrennt führen; ein Prio-1-Alarm ohne Stopp
erzeugt ein Ereignis mit duration 0 – bewusst.

## Quellen (mit Datum)
- VDMA 66412-1:2009-10, Kennzahlen; ISO 22400-2:2014, Zeitmodell (ADOT, ADET, APT) – iteh.ai Sample
- ISA-TR88.00.02-2022 (PackML), Zustandsmodell
- ANSI/ISA-18.2-2016 / EEMUA 191 4th ed. 11/2024 – Alarmflut 10 in 10 min
- Praxis Kurzstillstand-Schwelle: lemcon.tech „Verfügbarkeiten automatisch messen", 05.03.2026 (Betrieb definiert Ausfall selbst; Auflösung 1–5 s)
- docs/betriebsanweisung/BA-01-stoerungsmeldung.md (dieses Projekt)
