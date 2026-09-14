# Doku-Index

Automatisch erzeugt von autopilot/status.py – nicht von Hand pflegen.

## Entscheidungen (ADRs)
- [adr/0000-template.md](adr/0000-template.md) – ADR-NNNN: Titel: Datum: YYYY-MM-DD · Status: vorgeschlagen | akzeptiert | ersetzt
- [adr/0001-ereignisdefinition.md](adr/0001-ereignisdefinition.md) – ADR-0001: Störungsereignis – Beginn, Ende, Zusammenfassung: Datum: 2026-09-11 · Status: akzeptiert
- [adr/0002-entscheidungsbasis-replay.md](adr/0002-entscheidungsbasis-replay.md) – ADR-0002: Entscheidungsbasis durch Replay, nicht durch Erfindung: Datum: 2026-09-10 · Status: akzeptiert
- [adr/0003-orchestrierung.md](adr/0003-orchestrierung.md) – ADR-0003: Orchestrierung mit LangGraph: Datum: 2026-09-11 · Status: akzeptiert
- [adr/0004-rag.md](adr/0004-rag.md) – ADR-0004: RAG-Architektur – Chunking, Modell und Hybrid-Suche: Datum: 2026-09-12 · Status: akzeptiert
- [adr/0005-mcp-werkzeuge.md](adr/0005-mcp-werkzeuge.md) – ADR-0005: Sechs fachliche MCP-Werkzeuge statt generischem SQL: Datum: 2026-09-11 · Status: akzeptiert
- [adr/0006-konfidenzschwelle.md](adr/0006-konfidenzschwelle.md) – ADR-0006: Konfidenzschwelle und Konfidenzformel für Knoten 4: Datum: 2026-09-13 · Status: akzeptiert
- [adr/0007-observability.md](adr/0007-observability.md) – ADR-0007: Observability über Langfuse (self-hosted): Datum: 2026-09-13 · Status: akzeptiert
- [adr/0008-modell-und-kontext.md](adr/0008-modell-und-kontext.md) – ADR-0008: Claude Sonnet 5 über langchain-anthropic, Context Engineering je Knoten: Datum: 2026-09-11 · Status: akzeptiert
- [adr/0009-frontend.md](adr/0009-frontend.md) – ADR-0009: Vite + React + shadcn/ui + Recharts, FastAPI/SSE: Datum: 2026-09-11 · Status: akzeptiert
- [adr/0010-mes-nachrichtenformat.md](adr/0010-mes-nachrichtenformat.md) – ADR-0010: MES-Nachrichtenformat – OPC UA A&C + ISA-95 JSON: Datum: 2026-09-12 · Status: akzeptiert
- [adr/0011-beleg-pruefung-judge.md](adr/0011-beleg-pruefung-judge.md) – ADR-0011: Unabhängige Beleg-Prüfung der Maßnahmen (LLM-as-Judge): Datum: 2026-09-14 · Status: akzeptiert

## Betrieb
- [betriebsanweisung/BA-01-stoerungsmeldung.md](betriebsanweisung/BA-01-stoerungsmeldung.md) – Betriebsanweisung BA-01 · Störungsmeldung, Freigabe und Wiederanlauf – Verpackungslinie 1: Gültig ab: 2026-09-11 · Version 1.0 · Verantwortlich: Produktionsleitung Werk Nord · Geltungsbereich: Zuführung, Folienwickler,
- [chat_interface.md](chat_interface.md) – Schnittstelle Chat ↔ Projekt (manuell, drei Dateien): | Wann | Was ins Projektwissen / in den Chat | Befehl |
- [guardian.md](guardian.md) – Guardian – der Wächter vor jedem Commit: `autopilot/guardian.py` läuft als `pre-commit`-Hook (installiert durch `make install`) und blockiert den Commit,
- [orchestrator.md](orchestrator.md) – Orchestrator – Lane-Scheduler mit dauerhaftem Zustand: `autopilot/orchestrate.py` baut alle Pakete aus `autopilot/plan.yaml` spezifikationsbasiert, parallel je Lane,

## Tests
- [test_cases.md](test_cases.md) – Testfälle je Phase – Verifikation (V), Falsifikation (F), Review (R): Stand des Basisprojekts: **Basis-Testsuite grün** (aktuelle Anzahl siehe README/Statusseite). Neue Fälle je
- [test_strategy.md](test_strategy.md) – Teststrategie: Verifikation, Falsifikation, Review-Gates: Jede Einheit bekommt zwei Testarten. **Verifikation** zeigt, dass sie tut, was sie soll. **Falsifikation** versucht

## Verlauf
- [AENDERUNGEN.md](AENDERUNGEN.md) – Änderungen (Was / Warum / Alternativen): Chronologisch, neueste zuerst. Zahlen und Regelbereiche stehen bewusst nicht hier, sondern in den auto-Markern

## Weiteres
- [BACKLOG.md](BACKLOG.md) – Backlog – Phase 2 (Block 9): Fachliche Erweiterungen nach Abschluss der Kernarbeitspakete WP0–WP7.
- [CHANGELOG.md](CHANGELOG.md) – Changelog: Aus den Commits abgeleiteter Überblick über die gelieferten Arbeitspakete. Feinkörnige Begründungen
- [architecture.md](architecture.md) – Architektur – Zielbild und Verträge: ```mermaid
- [contracts/api.md](contracts/api.md) – API-Vertrag: Production Agent – SSE-Stream und Freigabe: Alle Pfade unterhalb von `http://localhost:8000`.
- [data_layer.md](data_layer.md) – Datenschicht Bronze→Silber→Gold: Technische Referenz für `src/production_agent/data/` (Simulator, Replay, Schema).
- [demo_script.md](demo_script.md) – Demo-Skript – 60 Minuten (Production Agent PoC): Fahrplan für das Interview am 17.09. Drei Blöcke: **12 min Live-Demo**, **30 min Entscheidungen**,
- [demo_walkthrough/README.md](demo_walkthrough/README.md) – UI-Walkthrough Agent-Tab (Mock) – LLM-as-Judge: Echter Browser-Durchlauf (Playwright, Chromium, LLM_MODE=mock) des Agent-Tabs mit der neuen
- [e2e.md](e2e.md) – Ende-zu-Ende-Replay: Der Ende-zu-Ende-Lauf prüft den kompletten LangGraph-Ablauf gegen die **echten** MES- und
- [ops.md](ops.md) – Ops-Cockpit: Lokale Steuerungsoberfläche für den Orchestrator-Betrieb. Unabhängig vom Produktionsleiter-Frontend.
- [plan.md](plan.md) – Projektplan – Scope, Budget, Gates: Minimalanforderungen: stehende Linie untersuchen, Alarme zu Ereignissen aggregieren, historisches Wissen abrufen,
- [references.md](references.md) – Externe Quellen: was übernommen wurde, wie und unter welcher Lizenz: Drei Stufen – nie „Repo klonen und anpassen":
- [stack.md](stack.md) – Stack und Entscheidungsgrundlage: Jede Zeile verweist auf eine ADR mit Alternativen, Kriterien und Quellen. Versionen: Stand 11.09.2026, vor Nutzung mit `pip index versions` 
- [testplan_e2e.md](testplan_e2e.md) – Testplan Ende-zu-Ende: Die Ende-zu-Ende-Fälle prüfen den kompletten LangGraph-Ablauf gegen die **echten** MES/RAG-Werkzeuge
