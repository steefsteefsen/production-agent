# UI-Walkthrough Agent-Tab (Mock)

Echter Browser-Durchlauf (Playwright, Chromium, LLM_MODE=mock) des Agent-Tabs: 
laufbegleitender Erzähltext je Knoten, Freigabe- und Ablehnungspfad. Erzeugt mit 
`python scripts/demo_walkthrough.py` bei laufender API (8000) und Vite (5173). 
Die Bilddateien und das Video sind lokale Verifikationsartefakte (per .gitignore nicht 
committet – Guardian S9 lässt Binärdateien nur unter docs/status/ oder docs/images/ zu).

## Screenshots

- **01_agent_tab.png** — Agent-Tab geöffnet: Steuerzeile (Ereignis 360, Modus mock), Fortschrittsleiste und die sieben Schritt-Karten im Zustand wartend.
- **02_lauf_erzaehltext.png** — Erzähltext synchron zur Karte: „Der Agent untersucht die stehende Linie Schritt für Schritt – er empfiehlt, er führt nicht aus.“
- **03_lauf_erzaehltext.png** — Erzähltext synchron zur Karte: „Linienstatus und Produktionsplan erfasst: 2 Aufträge im Plan.“
- **04_lauf_erzaehltext.png** — Erzähltext synchron zur Karte: „16 Alarme ausgewertet – Alarmflut erkannt, der Lauf verzweigt in den Wissensabruf.“
- **05_lauf_erzaehltext.png** — Erzähltext synchron zur Karte: „Historisches Wissen abgerufen: 5 ähnliche Vorfälle und 5 Wartungsdokumente.“
- **06_lauf_erzaehltext.png** — Erzähltext synchron zur Karte: „Ursache eingegrenzt: Hypothese STO-FOLIE bei Konfidenz 0.80.“
- **07_lauf_erzaehltext.png** — Erzähltext synchron zur Karte: „Wirkung geschätzt: 3.320 € geschätzte Wirkung, 1 gefährdete Aufträge.“
- **08_lauf_erzaehltext.png** — Erzähltext synchron zur Karte: „2 Maßnahmen abgeleitet, jede mit Vorfall-ID belegt.“
- **09_freigabeknoten.png** — Freigabeknoten erreicht: Maßnahmenliste mit Belegen (Beleg: ähnlicher Vorfall …) und Erzähltext zur Freigabe. Der Agent empfiehlt, der Mensch entscheidet.
- **10_karte.png** — Schritt-Karte „Linienstatus & Plan“ aufgeklappt: Live-Zusammenfassung, Funktion/Ausblick-Annotation und Payload-Detail.
- **11_karte.png** — Schritt-Karte „Alarme analysieren“ aufgeklappt: Live-Zusammenfassung, Funktion/Ausblick-Annotation und Payload-Detail.
- **12_karte.png** — Schritt-Karte „Wissen abrufen“ aufgeklappt: Live-Zusammenfassung, Funktion/Ausblick-Annotation und Payload-Detail.
- **13_karte.png** — Schritt-Karte „Ursache eingrenzen“ aufgeklappt: Live-Zusammenfassung, Funktion/Ausblick-Annotation und Payload-Detail.
- **14_karte.png** — Schritt-Karte „Wirkung schätzen“ aufgeklappt: Live-Zusammenfassung, Funktion/Ausblick-Annotation und Payload-Detail.
- **15_karte.png** — Schritt-Karte „Maßnahmen ableiten“ aufgeklappt: Live-Zusammenfassung, Funktion/Ausblick-Annotation und Payload-Detail.
- **16_abschluss_freigabe.png** — Abschluss nach Freigabe, reason_hit gegen die Gold-Wahrheit: „Untersuchung abgeschlossen. Ursache bestätigt gegen die verborgene Wahrheit (STO-FOLIE vs. Gold). Vollständiges Audit-Log verfügbar.“
- **17_abschluss_ablehnung.png** — Zweiter Lauf, Ablehnen: sauberer Abbruch, keine Maßnahme freigegeben. „Untersuchung abgebrochen. Keine Maßnahme freigegeben, die Empfehlung bleibt unausgeführt. Vollständiges Audit-Log verfügbar.“

## Auffälligkeiten

- Keine. Jede Schrittkarte erschien, der Erzähltext wechselte synchron, Freigabe- und Ablehnungspfad reagierten wie erwartet.
