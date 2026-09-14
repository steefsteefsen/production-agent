# UI-Walkthrough Agent-Tab (Mock) – LLM-as-Judge

Echter Browser-Durchlauf (Playwright, Chromium, LLM_MODE=mock) des Agent-Tabs mit der neuen 
Beleg-Prüfung (Knoten 7, LLM-as-Judge). Erzeugt mit `python scripts/demo_walkthrough.py` bei 
laufender API (8000) und Vite (5173). Die Bilddateien und das Video sind lokale 
Verifikationsartefakte (per .gitignore nicht committet – Guardian S9 lässt Binärdateien nur 
unter docs/status/ oder docs/images/ zu).

## Screenshots

- **01_agent_tab.png** — Agent-Tab: acht Karten inkl. neuer Karte 7 „Beleg-Prüfung“ vor der Freigabe.
- **02_lauf_erzaehltext.png** — Erzähltext synchron zur Karte: „Der Agent untersucht die stehende Linie Schritt für Schritt – er empfiehlt, er führt nicht aus.“
- **03_lauf_erzaehltext.png** — Erzähltext synchron zur Karte: „Linienstatus und Produktionsplan erfasst: 2 Aufträge im Plan.“
- **04_lauf_erzaehltext.png** — Erzähltext synchron zur Karte: „16 Alarme ausgewertet – Alarmflut erkannt, der Lauf verzweigt in den Wissensabruf.“
- **05_lauf_erzaehltext.png** — Erzähltext synchron zur Karte: „Historisches Wissen abgerufen: 5 ähnliche Vorfälle und 5 Wartungsdokumente.“
- **06_lauf_erzaehltext.png** — Erzähltext synchron zur Karte: „Ursache eingegrenzt: Hypothese STO-FOLIE bei Konfidenz 0.80.“
- **07_lauf_erzaehltext.png** — Erzähltext synchron zur Karte: „Wirkung geschätzt: 3.320 € geschätzte Wirkung, 1 gefährdete Aufträge.“
- **08_lauf_erzaehltext.png** — Erzähltext synchron zur Karte: „2 Maßnahmen abgeleitet, jede mit Vorfall-ID belegt.“
- **09_lauf_belegpruefung.png** — Erzähltext Beleg-Prüfung: „Ein zweites, unabhängiges Modell prüft jede Maßnahme gegen ihren Beleg – mit anderem Kontext als das vorschlagende Modell, damit es dessen Begründung nicht einfach übernimmt. Ergebnis: 2 von 2 bestätigt.“
- **10_beleg_alle_gruen.png** — Beleg-Prüfung-Karte und Freigabe-Gate: alle Maßnahmen „vom Judge bestätigt“ (4 grün, 0 rot).
- **11_abschluss_freigabe.png** — Abschluss nach Freigabe (reason_hit): „Untersuchung abgeschlossen. Ursache bestätigt gegen die verborgene Wahrheit (STO-FOLIE vs. Gold). Vollständiges Audit-Log verfügbar.“
- **12_beleg_judge_lehnt_ab.png** — ENTSCHEIDEND: Beleg-Prüfung mit rotem Badge „✗ vom Judge nicht bestätigt“ – der Judge stützt eine Maßnahme ohne Beleg NICHT; das Badge ist auch am Gate sichtbar.
- **13_beleg_judge_note.png** — Freigabe-Gate zeigt die Judge-Begründung zur abgelehnten Maßnahme.
- **14_abschluss_ablehnung.png** — Ablehnen-Pfad: sauberer Abbruch. „Untersuchung abgebrochen. Keine Maßnahme freigegeben, die Empfehlung bleibt unausgeführt. Vollständiges Audit-Log verfügbar.“

## Auffälligkeiten

- Keine. Die Beleg-Prüfung erschien als eigener Schritt; in Lauf A bestätigte der Judge alle Maßnahmen (grün), in Lauf B lehnte er die Maßnahme mit entferntem Beleg sichtbar ab (rotes Badge am Gate).
