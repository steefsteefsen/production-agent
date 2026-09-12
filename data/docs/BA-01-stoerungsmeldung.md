# Betriebsanweisung BA-01 · Störungsmeldung, Freigabe und Wiederanlauf – Verpackungslinie 1

Gültig ab: 2026-09-11 · Version 1.0 · Verantwortlich: Produktionsleitung Werk Nord · Geltungsbereich: Zuführung, Folienwickler,
Schneidstation, Siegelstation, Kartonierer, Palettierer sowie Schnittstelle zur vorgelagerten Abfüllanlage (UP1).

Diese Anweisung ist simuliert und Teil des Wartungswissens des Assistenzsystems. Sie beschreibt, was als Störung gilt, wer
meldet, wer freigibt und wie der Wiederanlauf abläuft.

## 1. Begriffe
- **Kurzstillstand**: Linie oder Station steht kürzer als 5 Minuten und es liegt kein Alarm der Priorität 1 vor. Kurzstillstände
  werden nicht gemeldet, sondern je Schicht gezählt (Leistungsverlust).
- **Störung (Störungsereignis)**: Station wechselt in Stopped, Held, Suspended oder Aborted und steht 5 Minuten oder länger –
  oder ein Alarm der Priorität 1 tritt auf, unabhängig von der Dauer. Eine Störung endet, wenn die Station 60 Sekunden stabil in
  Execute läuft. Steht sie innerhalb von 5 Minuten erneut, ist es dieselbe Störung.
- **Alarmflut**: 10 oder mehr Alarme innerhalb von 10 Minuten. Bei Alarmflut gilt: erst der Zustand der Stationen, dann die Alarme.
- **Vorgelagerte Anlage (UP1)**: Steht die Abfüllanlage, wird die Linie mit Grund EXT-UP geführt; die Ursache liegt nicht in der Linie.

## 2. Alarmprioritäten (ISA-18.2)
| Prio | Konsequenz | Reaktion | Beispiele |
|---|---|---|---|
| 1 | Sicherheit / Anlagenschaden | sofort, < 1 min | Not-Halt, Übertemperatur Antrieb, Schutztür während Execute |
| 2 | Stillstand innerhalb 10 min | < 10 min | Folienriss, Antriebsfehler, Siegelheizung |
| 3 | Qualität / Leistung | innerhalb der Schicht | Sensor verschmutzt, Schnittqualität, Produktstau |
| 4 | Hinweis | keine | Rolle fast leer, Kartonvorrat niedrig |

## 3. Meldung
1. Bediener quittiert den Alarm am Panel und prüft die angezeigte Station (Sichtprüfung). Er greift nicht in Antrieb, Elektrik oder
   Heizung ein.
2. Ist die Ursache nach Sichtprüfung nicht innerhalb von 5 Minuten behoben, ruft der Bediener den Schichtführer.
3. Der Schichtführer entscheidet über Maßnahmen an Mechanik und Material. Maßnahmen an Antrieb, Elektrik und Siegelheizung
   (Gründe STO-ANTRIEB, STO-ELEK, STO-SIEGEL) führt ausschließlich die Instandhaltung aus.
4. Übersteigt der erwartete Produktionsverlust 5 000 €, gibt zusätzlich die Produktionsleitung frei (Vier-Augen-Prinzip).

## 4. Assistenzsystem
Das Assistenzsystem schlägt Maßnahmen vor und nennt zu jeder Aussage Alarmcode, Vorfall-ID oder Regel. Es führt nichts aus.
Vorschläge mit Konfidenz unter dem eingestellten Wert (Standard 0,60) sind Hypothesen und keine Empfehlung. Ein Vorschlag ohne
Entscheidung verfällt nach 30 Minuten. Das System schlägt niemals das Überbrücken oder Deaktivieren von Schutzeinrichtungen,
Not-Halt oder Verriegelungen vor; solche Vorschläge sind als Fehler zu melden.

## 5. Wiederanlauf
1. Ursache beseitigt, Werkzeug und Material entfernt, Schutzeinrichtungen geschlossen.
2. Station quittieren; Wechsel Held → Execute nur durch Schichtführer oder Instandhaltung.
3. 60 Sekunden beobachten; bleibt die Station in Execute, ist die Störung beendet.
4. Grund im Störungsprotokoll wählen (Codeliste Abschnitt 6). Ohne Grund kein Abschluss.

## 6. Störungsgründe
STO-FOLIE Folienriss/Folienrolle · STO-SENSOR Sensorfehler · STO-ANTRIEB Antrieb/Lager · STO-ELEK Elektrik/Steuerung · STO-SIEGEL
Siegeltemperatur · MAT-LEER Zuführung leer · MAT-STAU Produktstau · MAT-KARTON Kartonvorrat leer · SETUP Formatwechsel ·
QUAL-HOLD Qualitätshalt · QUAL-NIO Ausschuss über Grenze · EXT-UP vorgelagerte Anlage steht · EXT-DOWN Abtransport · ORG Organisation

## 7. Protokollierung
Entscheidungen werden mit Zeit und Rolle protokolliert. Personen werden nicht im Klartext gespeichert; Auswertungen erfolgen je Linie,
nicht je Person (BetrVG § 87 Abs. 1 Nr. 6). Aufbewahrung 90 Tage.

## 8. Typische Störungen und bewährte Maßnahmen
| Code | Symptom | Erste Maßnahme (Bediener) | Weitere Maßnahme (Schichtführer / Instandhaltung) |
|---|---|---|---|
| E-4711 Folienriss | Folienwickler Held, Folgealarme E-4713 Bahnspannung | Sichtprüfung Rolle, Laufrichtung, Einspannung | Folie neu einfädeln, Rolle prüfen, Station quittieren |
| E-4730 Antrieb Übertemperatur | Folienwickler Aborted, Prio 1 | Abstand halten, nicht quittieren | Instandhaltung: Motor abkühlen lassen, Lager prüfen |
| E-5310 Schnittqualität | Schneidstation Stopped | Messer sichtprüfen | Messerwechsel bei Verschleiß > 200 min |
| E-6410 Sensor verschmutzt | Kartonierer Held, wiederholte Fehlsignale | Lichtschranke reinigen | Sensor justieren, Kabel prüfen |
| E-6430 Produktstau | Kartonierer Stopped, Rückstau bis Schneidstation | Stau räumen, Schutztür schließen | Ursache stromabwärts prüfen (Wurzelstation) |
