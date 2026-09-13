# Ende-zu-Ende-Replay

Der Ende-zu-Ende-Lauf prüft den kompletten LangGraph-Ablauf gegen die **echten** MES- und
RAG-Werkzeuge – nicht gegen Fixture-Funktionen. Grundlage ist der jüngste Replay-Fall aus
`downtime_events_gold`: die Replay-Uhr (`SIM_NOW`) steht kurz nach Störungsbeginn, die Gold-Zeile
(Dauer, Ursache, Maßnahme) bleibt für den Agenten verborgen und dient nur der Bewertung.

## Warum zusätzlich zu den Unit-Tests

Die Unit-Tests injizieren Werkzeuge als Python-Funktionen, die rohes JSON zurückgeben. Die echten
MCP-Werkzeuge kapseln ihr Ergebnis dagegen in eine `<tool_data>`-Hülle (Injection-Schutz). Vier
Integrationsfehler blieben deshalb unter den Fixture-Tests unsichtbar und traten erst im
Ende-zu-Ende-Lauf zutage:

- `_parse` löste die `<tool_data>`-Hülle nicht auf – alle Werkzeugergebnisse kamen leer an.
- `_extract_packml_state` nahm das erste Betriebsmittel statt der **stehenden** Station und kannte die
  `{"rows": …}`-Form nicht.
- `_top_alarm_codes` enthielt den **Erstalarm** nicht, sodass die Wissensabfrage den auslösenden Code
  verfehlen konnte.
- Knoten 6 stellte Dokumente vor die Vorfälle, sodass das Modell keine Vorfall-ID zum Belegen sah.

## Modell-Schalter

`LLM_MODE` steuert die beiden LLM-Knoten:

- `mock` (Standard): deterministisches Mock-LLM (`graph/mock_llm.py`) ohne API-Schlüssel – für CI und
  reproduzierbare Läufe.
- `live`: `ChatAnthropic` aus den Einstellungen (API-Schlüssel in `.env`).

`build_graph(llm=…)` sticht den Schalter (Tests injizieren eigene Chains).

## Ausführen

```
python -m production_agent.data.simulator      # Datenbank erzeugen
make e2e-mock                                  # LLM_MODE=mock python scripts/e2e_replay.py
make e2e-live                                  # LLM_MODE=live python scripts/e2e_replay.py (Demo)
```

Der Lauf meldet Alarmzahl und Alarmflut, gefundene Dokumente und ähnliche Vorfälle, wie viele
Maßnahmen eine Vorfall-ID belegen, ob die Ursache getroffen wurde und ob der Freigabeknoten erreicht
ist. Der Exit-Code ist nur dann 0, wenn ähnliche Vorfälle vorliegen, mindestens eine Maßnahme belegt
ist, der Freigabeknoten hält und die Ursache stimmt.
