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

Die konkreten Modell-IDs stehen zentral in `config.py` und sind über Umgebungsvariablen
überschreibbar: `LLM_MODEL_MAIN` (Knoten 4/6, Default `claude-sonnet-5`) und `LLM_MODEL_JUDGE`
(LLM-as-Judge/Klassifikation, Default `claude-haiku-4-5-20251001`). **Kostenentscheidung:** Die
Begründungsknoten laufen auf Sonnet statt Opus – Opus ist für die wiederholte Demo zu teuer, Sonnet
trägt die Begründungsqualität (siehe ADR-0008). Der `live`-Lauf verbraucht API-Kontingent.

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

## Agent-Tab – geführte Demo im Cockpit

Der Agent-Tab im React-Cockpit zeigt die Untersuchung als geführte Schrittfolge: je Graph-Knoten
eine Karte mit Live-Zusammenfassung aus dem SSE-Stream (`/investigations/stream`) und zwei
statischen Annotationen – **Funktion** (was der Knoten tut, über welchen Weg) und **Ausblick**
(Ausbaustufe nach Kauf). Der Umschalter „Demo-Notizen" blendet die Annotationen ein (Präsentation)
oder aus (Produktansicht). Der Modus mock/live kommt aus dem Backend-`LLM_MODE` und wird nur
angezeigt, nicht im Cockpit gesetzt.

Die Freigabe läuft über `interrupt()`/Resume: am Freigabeknoten hält der Graph, die Karte listet
Maßnahmen samt Belegen und geschätzter Wirkung; **Freigeben** oder **Ablehnen** setzt über
`/investigations/approve` fort. Nach dem Lauf vergleicht das Cockpit die Hypothese mit der
Gold-Wahrheit (`/investigations/gold/{event_id}`, nur für die Eval, kein Leck an den Agenten).

**Manueller Prüfpfad (LLM_MODE=mock):**

1. Backend `uvicorn production_agent.api.server:app` und Frontend `npm run dev` starten.
2. Cockpit öffnen, Tab **Agent**, Ereignis-ID `360`, **Untersuchung starten**.
3. Die sieben Karten füllen sich der Reihe nach; am Ende erscheint **Freigabe erforderlich**.
4. **Freigeben** → Abschlusskarte „regulärer Abschluss" mit Audit-Hinweis und Eval (`reason_hit`).
5. Erneut starten, diesmal **Ablehnen** → „sauberer Abbruch, kein Maßnahmen-Abschluss".

## Browser-Konsolenchecks (Pflicht bei UI-Änderungen)

Jede Änderung an den generierten HTML-Oberflächen (Agent-Cockpit, Ops-Cockpit, Präsentation) MUSS
durch die folgenden Playwright-Checks laufen, bevor sie als „fertig" gilt – 0 Browser-Konsolenfehler
ist Pflichtbedingung (HTTP 200 / ruff / pytest reichen NICHT, siehe docs/system_audit_2026-09-14.md).

Voraussetzung: Server laufen (`make run-api`, `make ui`, `make ops`), `LLM_MODE=mock`.

```bash
python scripts/ui_check/ops_check.py     # Ops-Cockpit :8010 – alle 4 Tabs, 0 Konsolenfehler
python scripts/ui_check/agent_check.py   # Agent-Tab :5173 – Lauf bis Freigabe, 0 Konsolenfehler
python scripts/demo_walkthrough.py       # ausführlicher erzählerischer Durchlauf (Screenshots)
```

Exit-Code 0 = bestanden. Screenshots/READMEs landen unter `docs/demo_walkthrough/` (Bilder gitignored,
Guardian S9). Beide Checks scheitern hart bei ≥1 Konsolenfehler – genau der Fall, der das Ops-Cockpit
unbemerkt unbedienbar gemacht hatte.
