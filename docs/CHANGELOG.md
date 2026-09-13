# Changelog

Aus den Commits abgeleiteter Überblick über die gelieferten Arbeitspakete. Feinkörnige Begründungen
(Was/Warum/Alternativen) stehen in [AENDERUNGEN.md](AENDERUNGEN.md); veränderliche Zahlen und Stände
in den auto-Markern der Doku, nicht hier.

## Arbeitspakete

### WP7 · Integration und Demo
- `docs/demo_script.md`: 60-Minuten-Fahrplan (Demo rückwärts vom Freigabeknoten, Entscheidungen je ADR, Fragenteil) mit wörtlich aufgenommenen Ehrlichkeitsgrenzen.
- ADR-Vollständigkeit über alle Kernthemen bestätigt (Orchestrierung, MCP-Werkzeuge, RAG, Daten/Replay, Modell, Konfidenz, Observability, Frontend).

### WP6 · Replay-Eval und Observability
- `evals/run_evals.py` vom Kostenschätzungs-Skelett zur echten Mock-Eval: Replay-Fälle über `replay.select_replay_cases`, Graph je Fall gegen die echten MES/RAG-Werkzeuge, Vergleich mit der Gold-Zeile über `replay.score`, deterministische Prüfungen (Freigabeknoten, keine `forbidden`-Maßnahme, Konfidenz-Obergrenze, Alarmflut→Wissenszweig, Werkzeugreihenfolge).
- `evals/report.md` und `evals/scenarios.json` aus echtem Lauf; Konfusionsmatrix Ursache.
- Optionaler Langfuse-Callback (`evals/langfuse_tracing.py`), nur aktiv bei aktiviertem Langfuse; `docker-compose.langfuse.yml`; CI-Stage `evals`; `docs/adr/0007-observability.md`.
- Zuvor: Testmatrix, zweiter Replay-Fall, Freigabe- und Ablehnungspfad über den SQLite-Checkpointer.

### WP5 · Agent-Tab im Cockpit
- Geführte Demo-Ansicht: je Graph-Knoten eine Schritt-Karte mit Live-Zusammenfassung aus dem SSE-Stream und den statischen Annotationen „Funktion" und „Ausblick".
- Freigabe-/Ablehnungskarte über `interrupt`/Resume, Abschlusskarte mit Audit-Hinweis und Eval, Fehlerbild mit Reconnect-Versuch.

### WP4 · AI4I-Regeln und Case-Based Reasoning
- `graph/rules.py`: die vier AI4I-Ausfallmodus-Regeln (TWF/HDF/PWF/OSF) als reine Funktionen über einen Sensor-Snapshot, mit Empty-Snapshot-Schutz.
- `graph/cbr.py`: Case-Based Reasoning per Jaccard-Ähnlichkeit über Alarmcodes, PackML-Zustand und Regelmodus; `docs/adr/0006-konfidenzschwelle.md`.
- Verdrahtung in den Graphen bewusst aufgeschoben (kein `wp/WP4`-Tag).

### WP3 · Ermittlungs-Workflow
- LangGraph-Ablauf mit den sieben Knoten, SSE-Auslieferung, `Hypothesis`/`RecommendedAction`, `interrupt()` am Freigabeknoten, SQLite-Checkpointer.

### WP2 · MCP-Werkzeuge und Wartungsdokumente
- MES-Server mit den fachlichen Werkzeugen (alle über den SQL-Guard, mit Zeilenlimits).
- `maintenance_docs`-Server: BM25-Suche mit RRF-Fusion, Ingest der Wartungsdokumente.

### WP0/WP1 · Fundament und Datenschicht
- Sicherheitsfundament (SQL-Guard, Injection-Guard, Action-Policy, Audit), deterministischer Simulator (Seed 42), Medallion Bronze→Silber→Gold, Replay-Uhr und Replay-Fälle.
- Entscheidungen in `docs/adr/` festgeschrieben (ADR-0001/0002 …).

### Autopilot und Infrastruktur (P, A, INF-*)
- Orchestrator, Status/Marker-Erzeugung, Coverage-Gate, Guardian (Sicherheit, Konsistenz, Doku-Aktualität), Ops-Cockpit, Abnahmetests, CI/pre-commit (ruff, bandit, gitleaks, detect-private-key).
