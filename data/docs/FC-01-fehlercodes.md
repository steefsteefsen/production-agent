# Fehlercode-Liste FC-01 · Verpackungslinie L1

Gültig ab: 2026-09-01 · Version 1.0 · Erstellt: Automatisierungstechnik Werk Nord

Diese Liste enthält alle Alarm- und Informationscodes der Verpackungslinie L1 nach ISA-18.2. Priorität 1 = sofortiger Handlungsbedarf (Sicherheit / Anlagenschaden), Priorität 4 = Hinweis.

## E-Codes – Fehlermeldungen (Error)

| Code | Priorität | Station | Kurzbeschreibung | Grund-Code |
|---|---|---|---|---|
| E-3302 | 2 | Schneidstation | Lichttaster verschmutzt / Sensorfehler | STO-SENSOR |
| E-3305 | 3 | Schneidstation | Schnittqualität unter Grenzwert (Folge) | STO-SENSOR |
| E-4711 | 2 | Folienwickler | Folienriss / Folienrolle falsch eingespannt | STO-FOLIE |
| E-4713 | 3 | Folienwickler | Bahnspannung außerhalb Toleranz (Folge) | STO-FOLIE |
| E-4720 | 3 | mehrere | Antriebsüberlast (allgemein) | STO-ANTRIEB |
| E-5101 | 1 | Siegelstation | Antrieb Überstrom – sofortiger Halt | STO-ANTRIEB |
| E-5102 | 2 | Siegelstation | Antrieb Überstrom Folge-Alarm | STO-ANTRIEB |
| E-5109 | 3 | Siegelstation | Antrieb Kommunikationsausfall (FU) | STO-ANTRIEB |
| E-6001 | 1 | Kartonierer | Sicherung / Steuerung ausgefallen | STO-ELEK |
| E-6002 | 2 | Kartonierer | Elektrik Folge-Alarm 1 | STO-ELEK |
| E-6003 | 3 | Kartonierer | Elektrik Folge-Alarm 2 | STO-ELEK |
| E-7001 | 2 | Siegelstation | Siegelnaht außerhalb Toleranz – Qualitätshalt | QUAL-HOLD |
| E-7002 | 3 | Siegelstation | Qualitätshalt Folge-Alarm | QUAL-HOLD |
| E-7101 | 2 | Siegelstation | Siegeltemperatur außerhalb Toleranz | STO-SIEGEL |
| E-7102 | 3 | Siegelstation | Siegelheizung Folge-Alarm | STO-SIEGEL |
| E-7201 | 3 | Siegelstation | Ausschussrate über Grenze | QUAL-NIO |
| E-7202 | 3 | Siegelstation | Ausschuss Folge-Alarm | QUAL-NIO |

## W-Codes – Warnmeldungen (Warning)

| Code | Priorität | Station | Kurzbeschreibung | Grund-Code |
|---|---|---|---|---|
| W-1001 | 3 | Zuführung | Zuführung leer – Produkt fehlt | MAT-LEER |
| W-1002 | 4 | Zuführung | Zuführung leer – Folge-Alarm | MAT-LEER |
| W-1201 | 3 | Kartonierer | Produktstau am Einlauf Kartonierer | MAT-STAU |
| W-1202 | 4 | Kartonierer | Produktstau Folge-Alarm | MAT-STAU |
| W-2101 | 3 | Folienwickler | Folienrolle fast leer (Restlaufzeit < 5 min) | STO-FOLIE |
| W-6401 | 4 | Kartonierer | Kartonmagazin fast leer (< 20 Kartons) | MAT-KARTON |
| W-6402 | 4 | Kartonierer | Kartonmagazin leer – Station Suspended | MAT-KARTON |
| W-9001 | 3 | Zuführung | Vorgelagerte Anlage UP1 steht | EXT-UP |
| W-9101 | 3 | Palettierer | Nachgelagerte Anlage / Abtransport steht | EXT-DOWN |

## I-Codes – Informationsmeldungen (Info)

| Code | Priorität | Station | Kurzbeschreibung | Grund-Code |
|---|---|---|---|---|
| I-0100 | 4 | Schneidstation | Formatwechsel / Rüstvorgang gestartet | SETUP |
| I-0200 | 4 | Palettierer | Bedienerpause / Schichtübergabe | ORG |

## Prioritätsmatrix (ISA-18.2 / IEC 62682)

| Priorität | Reaktionszeit | Konsequenz |
|---|---|---|
| 1 | sofort, < 1 min | Sicherheit / schwerer Anlagenschaden |
| 2 | < 10 min | Stillstand innerhalb 10 min |
| 3 | innerhalb der Schicht | Qualität / Leistung |
| 4 | keine Mindestzeit | Hinweis / Information |

## Zielverteilung

Gemäß ISA-18.2 sollte der Alarmanteil Prio 1 bei ≤ 5 %, Prio 2 bei ≤ 15 %, Prio 3 bei ≤ 30 % und Prio 4 bei ≤ 50 % liegen.
