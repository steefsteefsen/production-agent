# Wartungsanleitung MA-04 · Station Siegelstation – Verpackungslinie L1

Gültig ab: 2026-09-01 · Version 1.3 · Erstellt: Instandhaltung Werk Nord

## 1. Stationsbeschreibung

Die Siegelstation (Pos. 3) verschweißt die Folienenden zu einer hermetischen Naht. Die Prozesstemperatur (Standard 160–175 °C) und der Anpressdruck sind die entscheidenden Qualitätsparameter. Abweichungen führen zu offenen Packungen (QUAL-HOLD) oder Ausschuss (QUAL-NIO). Antriebs- und Elektrikstörungen an dieser Station sind meldepflichtig für Instandhaltung.

## 2. Typische Störungen

### E-7101 – Siegeltemperatur außerhalb Toleranz (Priorität 2)

Ursache: Heizung defekt, Temperaturfühler falsch kalibriert, Netzspannungsabfall.

Maßnahmen:
1. Station in Held – nicht quittieren bis Temperatur stabil.
2. Istwert am HMI ablesen; Soll 160–175 °C.
3. Instandhaltung benachrichtigen: Heizband und Temperaturfühler prüfen.
4. Erst quittieren, wenn Temperatur 5 Minuten im Toleranzband lag.

### E-7102 – Folge-Alarm Siegelheizung (Priorität 3)

Tritt auf, wenn E-7101 nach 10 Minuten nicht behoben. Gleiche Maßnahmen, Eskalation Schichtleiter.

### E-7001 – Siegelnaht außerhalb Toleranz / QUAL-HOLD (Priorität 2)

Qualitätshalt: Siegelnahtfestigkeit unter Mindestanforderung.

Maßnahmen:
1. Laufende Charge sperren (Rückhalteprotokoll).
2. Temperatur und Druck am HMI kontrollieren.
3. Qualitätsmuster ziehen und messen (Mindestfestigkeit 15 N/15 mm).
4. Freigabe durch Qualitätssicherung erforderlich.

### E-7002 – Folge-Alarm Qualitätshalt (Priorität 3)

Zweiter Qualitätshalt innerhalb der Schicht. Prozessunterbrechung und Überprüfung der Heizparameter.

### E-7201 – Ausschussrate über Grenze / QUAL-NIO (Priorität 3)

Ausschussrate überschreitet 2 %. Ursache: Temperaturdrift, Folienwechsel ohne Rekalibrierung.

Maßnahmen:
1. Letzte 10 Packungen prüfen (Sichtkontrolle und Zugtest).
2. Temperatur nachregeln (+/- 3 °C); Probelauf mit 20 Packungen.
3. Charge sperren, wenn Ausschuss > 5 % bestätigt.

### E-7202 – Folge-Alarm NIO (Priorität 3)

Wie E-7201; Instandhaltung prüft Anpressmechanismus.

### E-5101 – Antrieb Siegelstation Überstrom (Priorität 1 – sofortiger Halt)

Ursache: Lagerdefekt, Getriebe blockiert.

Maßnahmen:
1. Not-Halt gesetzt – kein Annähern an Antrieb.
2. Instandhaltung mit Spannungsfreiheit und Messgeräten.
3. Motor und Lager prüfen; ggf. Motoraustausch.
4. Freigabe durch Instandhaltungsleitung vor Wiederanlauf.

### E-5102 – Antrieb Überstrom Folge (Priorität 2)

Folge-Alarm nach E-5101. Gleiche Maßnahmen; keine Quittierung durch Bediener.

### E-5109 – Antrieb Kommunikationsausfall (Priorität 3)

Frequenzumrichter antwortet nicht. Steuerung neu starten (Instandhaltung).

### E-6001 – Sicherung / Steuerung Siegelstation (Priorität 1)

Spannungsausfall an Steuerungsebene.

Maßnahmen:
1. Instandhaltung (Elektrofachkraft) herbeirufen.
2. Ursache im Schaltschrank klären: Sicherung, FU, SPS.
3. Kein Wiederanlauf ohne Freigabe Elektrofachkraft.

### E-6002, E-6003 – Elektrik Folge-Alarme (Priorität 2/3)

Eskalationskette nach E-6001; Maßnahmen identisch.

### E-4720 – Antrieb Überlast Siegelstation (Priorität 3)

Folie klemmt im Siegelbereich oder Anpresseinheit blockiert.

## 3. Wartungsintervalle

| Intervall | Tätigkeit |
|---|---|
| täglich | Temperaturkurve letzte Schicht auswerten, Heizbänder sichtprüfen |
| wöchentlich | Anpressdruck messen, Temperaturfühler kalibrieren |
| monatlich | Heizband austauschen (nach Betriebsstunden-Plan), Antrieb schmieren |

## 4. Sicherheitshinweise

- Heizbänder und Siegelwerkzeug: Verbrennungsgefahr – Hitzeschutzhandschuhe.
- Spannungsfreischaltung vor jedem Eingriff am Heizkreis (IEC 61508).
- Qualitätsfreigabe liegt ausschließlich bei der Qualitätssicherung.
