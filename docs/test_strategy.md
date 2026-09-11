# Teststrategie: Verifikation, Falsifikation, Review-Gates

Jede Einheit bekommt zwei Testarten. **Verifikation** zeigt, dass sie tut, was sie soll. **Falsifikation** versucht
aktiv, sie zu brechen – der Test ist so formuliert, dass ein Sicherheits- oder Fachfehler ihn rot macht.
Ein Gate ist erst grün, wenn beide Arten grün sind. Danach folgt das **Review-Gate**: 10–15 Minuten Stefan, mit Checkliste.

## Ebenen und Werkzeuge

| Ebene | Was wird geprüft | Werkzeug | Beispiel Verifikation | Beispiel Falsifikation |
|---|---|---|---|---|
| Unit | Guards, Regeln, Formeln | pytest | SELECT auf Allowlist geht durch | DELETE, PRAGMA, fremde Tabelle → SqlGuardError |
| Daten | Medallion, Replay | pytest + kleine Simulator-DB (Seed 7) | Gold ≥ 100 Ereignisse, jede Zeile mit Herkunft | Ereignis ohne Bronze-Herkunft, PackML-Zustand außerhalb der vier Stopp-Zustände |
| MCP-Protokoll | Werkzeuge über das Protokoll | fastmcp `Client(server)` in-memory, kein Subprozess | 6 Werkzeuge, jede Antwort in `<tool_data trusted="false">` | Schreib-/SQL-Werkzeug existiert; laufende Störung leckt in die Historie; Ergebnis ist kein gültiges JSON |
| Trajektorie | Reihenfolge Knoten/Werkzeuge | LangGraph `stream(stream_mode="updates")` + **agentevals** Trajectory-Match (strict / unordered / subset / superset) | Alarmflut-Lauf entspricht Referenz strikt | ruhige Linie nimmt den RAG-Zweig; verbotene Maßnahme erreicht die Freigabe; Freigabe wird übersprungen |
| Ergebnis | Vorhersage gegen Wahrheit | Replay-Eval (`replay.score`) | Ursachentrefferquote, Dauerfehler | Konfidenz über Formel; Empfehlung unter Schwelle |
| LLM-Knoten | Struktur der Ausgabe | pytest mit gemocktem Modell; optional agentevals LLM-as-Judge | Hypothesis validiert gegen Pydantic-Schema | Modell erhöht Konfidenz → Nachbedingung schlägt an |

Warum agentevals: MIT, von LangChain, versteht LangGraph-Nachrichten direkt, vier Match-Modi ohne LLM, LLM-as-Judge
optional. DeepEval (ToolCorrectness) und RAGAS (Agent-Metriken) wären die Alternativen; Inspect (UK AISI) ist für
Benchmarks gebaut, nicht für pytest-Gates. Für die MCP-Ebene braucht es kein Framework – der In-Memory-Client von
fastmcp testet den Server wie ein echter Client, nur ohne Prozessstart.

## Was ein Falsifikationstest schon gefunden hat
`max_tool_result_chars` schnitt auf Zeichenebene und erzeugte ungültiges JSON. Der Test `test_row_limit_is_hard`
wurde rot; die Kürzung läuft jetzt auf Zeilenebene. Diese Geschichte gehört in die Präsentation.

## Wächter vor dem Commit
Siehe `docs/guardian.md` – Sicherheit, Konsistenz und Doku-Aktualität werden vor jedem Commit deterministisch geprüft.

## Review-Gate je Arbeitspaket (Stefan, 10–15 min)
Siehe `autopilot/tasks.yaml` → `review_gate`. `python autopilot/run.py --review` hält nach jedem grünen Gate an,
zeigt die Checkliste und wartet auf dein OK.
