# Architektur-Referenz — ein Abschnitt je Paket

Diese Seite ist die **Landkarte des Codes**: je Paket kurz, was es tut, wo es liegt und welche ADR
die Entscheidung begründet. Sie **dupliziert nichts** — Zielbild und Verträge stehen in
[architecture.md](architecture.md) und [contracts/api.md](contracts/api.md), veränderliche Zahlen
(Testanzahl, Schwellen) in der [Statusseite](status/index.html)/README bzw. in `decisions.yaml`.

Quelle aller fachlichen Entscheidungen ist `decisions.yaml` (nur lesen). Alle Entscheidungsprotokolle
liegen unter [adr/](adr/).

## Datenfluss (Überblick)
Simulator → SQLite (Bronze→Silber→Gold) → MCP-Werkzeuge → LangGraph-Ablauf → FastAPI/SSE →
React-Cockpit; die Freigabe hält den Graphen an (`interrupt()`), der Mensch entscheidet. Das
gezeichnete Zielbild steht in [architecture.md](architecture.md); die Replay-Uhr-Begründung in
[ADR-0002](adr/0002-entscheidungsbasis-replay.md).

## MCP-Server — `src/production_agent/mcp/`
Drei fachlich geschnittene Server (kein generisches SQL für das LLM); Begründung in
[ADR-0005](adr/0005-mcp-werkzeuge.md), Nachrichtenformat in
[ADR-0010](adr/0010-mes-nachrichtenformat.md).
- **`mes_server.py`** (Server `mes`) — Live-Sicht der Linie: Linienstatus/PackML, aktive Alarme,
  Produktionsplan. Jede Abfrage läuft über den SQL-Guard und liest die Replay-Uhr `SIM_NOW`.
- **`rag_server.py`** (Server `knowledge`) — historisches Wissen: Dokumentsuche, ähnliche Vorfälle,
  Alarmverlauf. BM25 + Vektor-Suche (sentence-transformers) mit RRF-Fusion; RAG-Details in
  [ADR-0004](adr/0004-rag.md).
- **`business_rules`** — regelbasierte Wirkungsschätzung (AI4I-Regeln + Case-Based Reasoning), kein
  ML-Training.

## Graph-Ablauf — `src/production_agent/graph/`
- **`workflow.py`** — der Ablauf ist **streng linear** (kein `add_conditional_edges`);
  Entscheidungen fallen INNERHALB der Knoten, nicht als Graph-Verzweigung. Der Freigabeknoten ist
  immer ein `interrupt()` mit Checkpointer-Resume. Orchestrierung/Modellwahl in
  [ADR-0003](adr/0003-orchestrierung.md) und [ADR-0008](adr/0008-modell-und-kontext.md).
- **`state.py`** — `AgentState`, der Zustand einer Untersuchung.
- **`rules.py`**, **`cbr.py`** — regelbasierte Wirkungsschätzung und Case-Based Reasoning.
- **`judge.py`** — unabhängige Beleg-Prüfung der Maßnahmen (LLM-as-Judge), Begründung in
  [ADR-0011](adr/0011-beleg-pruefung-judge.md); verzweigt NICHT, das Ergebnis wird nur angezeigt.
- **`prompts.py`**, **`structured.py`**, **`mock_llm.py`** — Prompts je Knoten, strukturierte
  Ausgaben, deterministisches Mock-LLM für `LLM_MODE=mock` (Tests/Demo ohne API-Key).

## Sicherheitsschicht — `src/production_agent/security/`
Der Agent EMPFIEHLT, er FÜHRT NICHT AUS; jede Stelle ist eng geschnitten:
- **`sql_guard.py`** — nur SELECT, Tabellen-Allowlist, Zeilenlimit, SQLite `mode=ro`. Kein freies SQL
  fürs LLM.
- **`injection_guard.py`** — kapselt jedes Werkzeugergebnis als untrusted Daten
  (`sanitize_tool_result`), markiert Injection-Muster, kürzt.
- **`action_policy.py`** — klassifiziert Maßnahmen (`inform` / `approval_required` / `forbidden`) und
  hält die Konfidenzschwelle ([ADR-0006](adr/0006-konfidenzschwelle.md)); Schritt 7 ist immer die
  Freigabe.
- **`audit.py`** — JSONL-Audit jedes Werkzeugaufrufs und jeder Freigabe.

## API — `src/production_agent/api/`
- **`server.py`** — FastAPI + SSE: Untersuchung starten/streamen, Freigabe (`interrupt`-Resume),
  Zustand aus dem Checkpointer, Konfiguration, RAG-/Observability-Endpunkte. Der SSE-/Freigabe-Vertrag
  steht in [contracts/api.md](contracts/api.md).
- **`mes_router.py`** — nur lesende, guard-geschützte MES-Endpunkte (Linienstatus zur Replay-Zeit,
  Gold-Ereignisse, Herkunftskette); Observability in [ADR-0007](adr/0007-observability.md).

## Frontend — `frontend/src/`
- **`main.tsx`** — pfadbasiertes Routing (SPA): `/` Cockpit, `/presentation` Walkthrough, `/freigabe`
  Freigabe-Seite. Stack/Begründung in [ADR-0009](adr/0009-frontend.md).
- **`Cockpit.tsx`** — Sechs-Tab-Cockpit (Bediener, Live-Daten, MCP, Wissen/RAG, Sicherheit,
  Konfiguration) mit echten Daten über die API.
- `presentation/Presentation.tsx`, `components/ApprovalPage.tsx` — Walkthrough und eigenständige
  Freigabe-Seite. (`App.tsx` ist unbenutzt, siehe README „Bekannte Altlasten".)

## Datenschicht — `src/production_agent/data/`
Simulator (Seed 42), Replay-Uhr/-Fälle und Bronze→Silber→Gold-Schema; technische Referenz in
[data_layer.md](data_layer.md), Ereignisdefinition in [ADR-0001](adr/0001-ereignisdefinition.md).

## Betrieb & Wächter
- **`autopilot/`** — Orchestrator, Statusgenerator und der **Guardian** (pre-commit-Wächter);
  Regeln in [guardian.md](guardian.md), Ops-Oberfläche in [ops.md](ops.md).
