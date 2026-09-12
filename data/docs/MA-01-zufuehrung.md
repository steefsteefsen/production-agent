# Wartungsanleitung MA-01 · Station Zuführung – Verpackungslinie L1

Gültig ab: 2026-09-01 · Version 1.1 · Erstellt: Instandhaltung Werk Nord

## 1. Stationsbeschreibung

Die Zuführung (Pos. 0) transportiert das zu verpackende Produkt vom Abfüller (vorgelagerte Anlage UP1) auf das Einlaufband der Linie. Zustand Execute erfordert einen kontinuierlichen Produktfluss. Bei Materialleerlauf (W-1001) wechselt die Station nach Suspended; nach Befüllung wird sie automatisch quittiert, sofern kein Folge-Alarm vorliegt.

## 2. Typische Störungen

### W-1001 – Zuführung leer

Ursache: Produktbehälter leer oder Abfüllanlage UP1 steht (dann statt W-1001 der Code W-9001).

Maßnahmen:
1. Bestand am Pufferbehälter prüfen.
2. Rückmeldung vom Bediener Abfüllanlage einholen.
3. Behälter wechseln oder Produkt nachfüllen.
4. Freigabe durch Schichtführer; Station quittieren.

### W-1002 – Zuführung leer, Folge-Alarm

Tritt auf, wenn W-1001 nicht innerhalb von 3 Minuten behoben wird. Prozedur identisch mit W-1001; Eskalation an Schichtführer.

### W-9001 – Vorgelagerte Anlage steht (EXT-UP)

Ursache: Abfüllanlage UP1 hat Betriebsstörung gemeldet.

Maßnahmen:
1. Kommunikation mit Bediener UP1 aufnehmen.
2. Linie in Suspended belassen; kein Eingriff an L1 notwendig.
3. Wartezeit in Störungsprotokoll unter Grund EXT-UP dokumentieren.
4. Sobald UP1 wieder Execute signalisiert, Zuführung quittieren.

## 3. Wartungsintervalle

| Intervall | Tätigkeit |
|---|---|
| täglich | Sichtprüfung Förderbänder, Reinigung Sensoren am Einlauf |
| wöchentlich | Schmierung Lagerböcke, Prüfung Bandspannung |
| monatlich | Prüfung Anlagenverkabelung, Anlagenprotokoll archivieren |

## 4. Sicherheitshinweise

- Schutzgitter nicht im Betrieb öffnen (Not-Halt-Pflicht).
- Eingriffe am Antrieb nur durch Instandhaltung (STO-ANTRIEB-Verfahren).
- Persönliche Schutzausrüstung: Sicherheitsschuhe, Handschuhe.
