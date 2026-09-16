# Production Agent PoC

Untersuchung einer stehenden Produktionslinie: simulierte MES-Daten → Alarmanalyse → historisches Wissen → Wirkungsschätzung → sichere Maßnahmenempfehlung mit menschlicher Freigabe.

Stack: LangGraph · FastMCP (drei MCP-Server: mes/knowledge/business_rules) · Anthropic Claude · FastAPI/SSE · Vite/React · Langfuse · SQLite (Bronze→Silber→Gold)

Projektstatus (automatisch erzeugt): [docs/status/index.html](docs/status/index.html)

## Setup von Null
```bash
git clone <repo-url> production-agent && cd production-agent
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev,embeddings]'                  # embeddings ist für den Demo-Pfad Pflicht (Vektor-Suche)
cp .env.example .env                                # ANTHROPIC_API_KEY eintragen (nur für LLM_MODE=live nötig)
python -m production_agent.data.simulator           # Störungshistorie → data/gold/mes.sqlite (Gold, ADR-0001)
python -m production_agent.mcp.rag_server --ingest  # Wartungsdokumente in den BM25-/Vektor-Index laden
cd frontend && npm install && cd ..                 # Frontend-Abhängigkeiten
```
`make install-demo` fasst die Python-Schritte zusammen (CPU-Torch + embeddings + ingest).
Konfiguration steht in `settings.env` (committet), Geheimnisse in `.env` (gitignored). `.env` enthält nur Schlüssel, die auf KEY/SECRET/TOKEN/PASSWORD enden.

## Demo starten — Reihenfolge & Timing
```bash
make run-api                    # 1. FastAPI + SSE auf Port 8000
cd frontend && npm run dev      # 2. React-Cockpit (Vite) auf Port 5173
make ops                        # 3. optional: internes Ops-Cockpit auf Port 8010
```
> **Wichtig zum ersten Start:** Der ERSTE `make run-api` lädt beim Import von `sentence-transformers`
> das Embedding-Modell und braucht dadurch rund anderthalb bis zwei Minuten. **Nicht abbrechen** —
> warten, bis in der Konsole `Application startup complete` erscheint. Folgestarts sind schnell
> (Modell gecacht).

**Umgebungsbesonderheit `--reload`:** In manchen Umgebungen re-exect der uvicorn-Reloader mit dem
falschen (User-Site-)`uvicorn` und bricht mit `ModuleNotFound: production_agent` ab. Workaround: ohne
`--reload` starten, z. B. `python -m uvicorn production_agent.api.server:app --host 127.0.0.1 --port 8000`.
Der Produktivpfad ist identisch.

Der Modus (mock/live) kommt aus `LLM_MODE` (`settings.env`/`.env`) und wird im Cockpit nur angezeigt.
Ohne API-Key läuft der Mock-Pfad; der kostenpflichtige Live-Lauf ist manuell.

## URLs im Browser
| URL | Inhalt |
|---|---|
| http://localhost:5173 | Cockpit / Bediener-Tab (Hauptdemo) |
| http://localhost:5173/presentation | Geführter Interview-Walkthrough |
| http://localhost:5173/freigabe | Eigenständige Freigabe-Seite |
| http://localhost:5173/pitch.html | Business-Pitch (statische Seite) |
| http://localhost:8010 | Ops-Cockpit (intern, nur 127.0.0.1) |

## Architektur auf einen Blick
- **Drei MCP-Server** (fachlich geschnitten, `src/production_agent/mcp/`): `mes` (Live-Linienstatus,
  Alarme, Produktionsplan), `knowledge` (Dokumentsuche, ähnliche Vorfälle, Alarmverlauf),
  `business_rules` (regelbasierte Wirkungsschätzung).
- **Linearer Graph:** `graph/workflow.py` verdrahtet die Knoten streng linear — **kein
  `add_conditional_edges`**; Entscheidungen fallen INNERHALB der Knoten, nicht als Graph-Verzweigung.
  Der Freigabeknoten ist immer ein `interrupt()`. Begründung in [docs/adr/](docs/adr/).
- **LLM_MODE=mock|live:** `mock` ist deterministisch (kein API-Key, für Tests/Demo), `live` nutzt
  Anthropic Claude. Umschaltung über `LLM_MODE`.
- Der Agent **empfiehlt, er führt nicht aus:** jede Maßnahme läuft durch `security/action_policy.py`.

## Architektur
```mermaid
flowchart LR
    Sim[Simulator<br/>Seed 42] --> DB[(SQLite<br/>Bronze→Silber→Gold)]
    subgraph Backend
      API[FastAPI + SSE] --> Graph[LangGraph-Workflow<br/>interrupt am Freigabeknoten]
      Graph --> MES[MCP mes<br/>Werkzeuge über SQL-Guard]
      Graph --> RAG[MCP maintenance_docs<br/>BM25 + Vektor, RRF]
    end
    MES --> DB
    RAG --> Qdrant[(Qdrant-Index)]
    API <--> Cockpit[React-Cockpit / Vite]
    Graph -.optional.-> Langfuse[(Langfuse-Tracing)]
    Graph -.Freigabe.-> Mensch((Mensch))
```
Der Agent empfiehlt, er führt nicht aus: jede Maßnahme läuft durch die Action-Policy, der Freigabeknoten ist immer ein `interrupt()`. Details in [docs/adr/](docs/adr/).

## Ops-Cockpit

```bash
make ops   # startet http://localhost:8010
```

Lokale Steuerungsoberfläche für Stefan (unabhängig vom Produktionsleiter-Frontend).
Vier Tabs: **Ablauf** (WP-Kacheln in Zustandsfarbe, Live-Log, Journal), **Stand** (Kennzahlen, Aktionen),
**Konfiguration** (decisions.yaml read-only, editierbare Felder schreiben `config/runtime.yaml` + Audit),
**Präsentation** (bettet `docs/presentation/index.html` ein).
Nur 127.0.0.1; keine Shell-Freitexteingaben; jede Aktion in `config/ops_audit.jsonl` protokolliert.
Dokumentation: [docs/ops.md](docs/ops.md).

## Tests
```bash
make test                    # gesamte Testsuite (<!-- auto:tests -->423<!-- /auto:tests --> Tests) mit Coverage-Gate, läuft ohne API-Key
pytest -q -m e2e tests/e2e   # Regressionssuite gegen den ECHTEN Demo-Pfad (BASE_URL gesetzt, Server läuft)
pytest -q -m embeddings tests/test_vector_search_demo.py   # erzwingt die Vektor-Suche (Demo-Pflicht)
```
Die e2e-Regressionssuite (`tests/e2e/test_known_bugs.py`) prüft je einen bestätigten Bug gegen den
echten Default-Pfad (kein `MCP_VIA_PROTOCOL=0`-Umgehen); sie ist im CI-e2e-Job eingebunden.

## Bekannte Altlasten (bewusst nicht entfernt)
- `frontend/src/App.tsx` ist **unbenutzt**: der Einstieg `frontend/src/main.tsx` importiert nur noch
  `Cockpit.tsx`, `presentation/Presentation.tsx` und `components/ApprovalPage.tsx`. Die Datei bleibt
  bewusst liegen (kein Löschen in der Interview-Vorbereitung); sie hat keine Wirkung auf die App.

## Die Entscheidungsbasis (ADR-0002)
Ein Simulator erzeugt 90 Tage Historie inklusive Auflösung und schreibt sie durch Bronze → Silber → Gold. „Jetzt" ist eine Replay-Uhr
5 Minuten nach Beginn eines Gold-Ereignisses: alles davor ist Historie mit bekannter Lösung, das Ereignis selbst ist offen, seine
Gold-Zeile die verborgene Wahrheit. Historie und aktueller Fall stammen aus derselben Verteilung – und die Eval (Vorhersage ↔ Gold)
fällt gratis ab. Alle Stellschrauben stehen in `decisions.yaml`.

## Was hier schon fertig ist (Sicherheitsfundament)
| Modul | Zweck |
|---|---|
| `config.py` | Settings aus settings.env + .env (SecretStr), Replay-Uhr `SIM_NOW`, Schwellen |
| `graph/state.py` | AgentState – der Zustand einer Untersuchung |
| `api/server.py` | FastAPI: Untersuchung starten, Freigabe (409 ohne wartenden Knoten) |
| `security/sql_guard.py` | SELECT-only, Tabellen-Allowlist, Row-Limit, SQLite `mode=ro` |
| `security/injection_guard.py` | Werkzeugergebnisse als untrusted Daten kapseln, Injection-Muster markieren, kürzen |
| `security/action_policy.py` | Maßnahmen klassifizieren (inform / approval_required / forbidden), Konfidenzschwelle |
| `security/audit.py` | JSONL-Audit jedes Tool-Aufrufs und jeder Freigabe |
| `graph/workflow.py` | linearer Ablauf (kein `add_conditional_edges`), Entscheidung in den Knoten, `interrupt()` am Freigabeknoten, Checkpointer |
| `mcp/mes_server.py` | fachliche Werkzeuge (Anzahl <!-- auto:tools_mes -->3<!-- /auto:tools_mes -->), alle über den Guard |
| `mcp/rag_server.py` | BM25 + Vektor-Suche (sentence-transformers) mit RRF-Fusion |
| `data/simulator.py`, `data/replay.py` | deterministischer MES-Simulator (Seed 42), Replay-Uhr, Replay-Fälle, Scoring |
| `autopilot/status.py` | erzeugt docs/status/ und füllt die auto-Marker in der Doku (Fakten statt Handarbeit) |
| `autopilot/guardian.py` | pre-commit: Sicherheit, Konsistenz, Doku-Aktualität – blockiert den Commit (Regeln siehe docs/guardian.md) |
| `autopilot/` | tasks.yaml + run.py: WPs unbeaufsichtigt mit `claude -p`, Gate + Review-Gate je WP, journal.md/json + Commit je WP, status.json fürs Cockpit |
| `docs/test_strategy.md`, `docs/references.md` | Verifikation/Falsifikation je Ebene; Regeln für externe Quellen (Abhängigkeit / Muster / nie) |
| `.claude/agents/`, `.claude/settings.json` | fünf Subagents mit Verzeichnisgrenzen, Rechte-Allowlist |
| CI / pre-commit | ruff, bandit, gitleaks, detect-private-key |

Die Arbeitspakete WP0–WP7 stehen in `autopilot/tasks.yaml`; die Entscheidungsgrundlage in `docs/stack.md` und `docs/adr/`.

## Stand
<!-- auto:stand -->
- fertig: 13 von 16 Paketen
- offen: WP4, WP6, WP7
- Fortschritt: 85 % — siehe [Statusseite](docs/status/index.html)
<!-- /auto:stand -->

Guardian-Regeln (automatisch aus dem Guardian-Docstring):
<!-- auto:guardian_rules -->
Regeln: S1–S9, K1–K10, D1–D9.

- **S1**: keine Secrets, keine .env committet
- **S2**: keine verbotene Bibliothek der Ausschlussliste (CLAUDE.md)
- **S3**: drei MCP-Server (mes=3 Live, knowledge=3 Suche/Verlauf, business_rules=1 Regel), kein *sql/query/write/exec*
- **S4**: schema.sql und ALLOWED_TABLES identisch
- **S5**: decisions.yaml eingefroren (Hash; Aenderung nur mit GUARDIAN_ALLOW_DECISIONS=1)
- **S6**: Sicherheitsmodul geaendert -> Sicherheits-, Protokoll- und Trajektorientests gruen
- **S7**: kein .env-Wert (len>=8) in anderer getrackter/gestagter Datei; S7b .env nur KEY|SECRET|TOKEN|PASSWORD-Schluessel; S7c .env.example-Werte enden auf -EXAMPLE
- **S8**: keine Begriffe der Oeffentlichkeits-Blocklist (.guardian_public/blocklist.sha256)
- **S9**: gestagte Binaerdateien nur unter docs/status/ oder docs/images/ und < 500 KB
- **K1**: jedes src-Modul hat eine Testdatei mit Verifikations- und Falsifikationstest
- **K2**: ruff und bandit sauber
- **K3**: Commit-Message folgt der Konvention (commit-msg-Hook)
- **K4**: Coverage: gesamt >=80, security >=95, mes_server/workflow >=85
- **K5**: jede entry-Zeile in .pre-commit-config.yaml beginnt mit .venv/bin/python
- **K6**: tasks.yaml-WPs stehen in plan.yaml, Abhaengigkeiten sind aufloesbar und azyklisch
- **K7**: tests/acceptance/ nur mit GUARDIAN_ALLOW_ACCEPTANCE=1 aenderbar (Abnahmetests = Spezifikation)
- **K8**: autopilot/ geaendert -> autopilot/selfcheck.py grün (GUARDIAN_SKIP_K8=1 unterdrueckt)
- **K9**: gelernte Rechte (state/denied.json) noch nicht erlaubt -> WARNUNG mit Allow-Vorschlag (blockiert nie)
- **K10**: jeder {{a.b}}-Platzhalter in tasks.yaml existiert in decisions.yaml (Renderfehler = Nachtlauf tot)
- **D1**: jedes src-Modul ist in README oder docs/ namentlich erwaehnt
- **D2**: jede ADR hat Kontext / Optionen / Entscheidung / Konsequenzen
- **D3**: src geaendert -> auch docs/, README oder tests/ geaendert
- **D4**: Aenderungen in src/autopilot/adr/contracts/decisions: AENDERUNGEN.md gestaged, Datum heute, alle fuenf Felder, kein Platzhalter
- **D5**: Titel oberster AENDERUNGEN.md-Eintrag gleich erster Commit-Zeile (Pruefung commit_check.py)
- **D6**: docs/status/status.json gestaged, frisch (<10 min), commit leer oder == HEAD
- **D7**: jeder auto-Marker in getrackten *.md hat den von status.py berechneten Wert
- **D8**: ausserhalb Markern keine getippten Zahlen/Regelbereiche/Coverage in README.md und docs/*.md
- **D9**: README.md hat Abschnitt "## Stand" mit nicht-leerem auto:stand-Marker
<!-- /auto:guardian_rules -->

## Lizenz
MIT, © 2026 Stefan Hüllinghorst – siehe LICENSE.
