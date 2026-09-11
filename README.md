# Production Agent PoC

Untersuchung einer stehenden Produktionslinie: simulierte MES-Daten → Alarmanalyse → historisches Wissen → Wirkungsschätzung → sichere Maßnahmenempfehlung mit menschlicher Freigabe.

Stack: LangGraph · FastMCP (2 Server) · Anthropic Claude · FastAPI/SSE · Vite/React · Langfuse · SQLite (Bronze→Silber→Gold)

## Schnellstart
```bash
python -m venv .venv && source .venv/bin/activate
make install                            # deps + pre-commit
cp .env.example .env                    # API-Key eintragen
python -m production_agent.data.simulator   # 360 Störungsereignisse → data/gold/mes.sqlite
make test                               # 16 Tests, laufen ohne API-Key
python autopilot/run.py --dry-run       # Prompts der Arbeitspakete ansehen, dann ohne --dry-run laufen lassen
```

## Die Entscheidungsbasis (ADR-0002)
Ein Simulator erzeugt 90 Tage Historie inklusive Auflösung und schreibt sie durch Bronze → Silber → Gold. „Jetzt" ist eine Replay-Uhr
5 Minuten nach Beginn eines Gold-Ereignisses: alles davor ist Historie mit bekannter Lösung, das Ereignis selbst ist offen, seine
Gold-Zeile die verborgene Wahrheit. Historie und aktueller Fall stammen aus derselben Verteilung – und die Eval (Vorhersage ↔ Gold)
fällt gratis ab. Alle Stellschrauben stehen in `decisions.yaml`.

## Was hier schon fertig ist (Sicherheitsfundament)
| Modul | Zweck |
|---|---|
| `config.py` | Settings aus .env (SecretStr), Replay-Uhr `SIM_NOW`, Schwellen |
| `graph/state.py` | AgentState – der Zustand einer Untersuchung |
| `api/server.py` | FastAPI: Untersuchung starten, Freigabe (409 ohne wartenden Knoten) |
| `security/sql_guard.py` | SELECT-only, Tabellen-Allowlist, Row-Limit, SQLite `mode=ro` |
| `security/injection_guard.py` | Werkzeugergebnisse als untrusted Daten kapseln, Injection-Muster markieren, kürzen |
| `security/action_policy.py` | Maßnahmen klassifizieren (inform / approval_required / forbidden), Konfidenzschwelle |
| `security/audit.py` | JSONL-Audit jedes Tool-Aufrufs und jeder Freigabe |
| `graph/workflow.py` | 7 Knoten, Verzweigung bei Alarmflut, `interrupt()` am Freigabeknoten, Checkpointer |
| `mcp/mes_server.py` | 6 fachliche Werkzeuge, alle über den Guard |
| `mcp/rag_server.py` | BM25-Suche + RRF-Fusion (Vektorseite folgt in WP2) |
| `data/simulator.py`, `data/replay.py` | deterministischer MES-Simulator (Seed 42), Replay-Uhr, Replay-Fälle, Scoring |
| `autopilot/guardian.py` | pre-commit: Sicherheit (S1–S6), Konsistenz (K1–K2), Doku-Aktualität (D1–D3) – blockiert den Commit |
| `autopilot/` | tasks.yaml + run.py: WPs unbeaufsichtigt mit `claude -p`, Gate + Review-Gate je WP, journal.md/json + Commit je WP, status.json fürs Cockpit |
| `docs/test_strategy.md`, `docs/references.md` | Verifikation/Falsifikation je Ebene; Regeln für externe Quellen (Abhängigkeit / Muster / nie) |
| `.claude/agents/`, `.claude/settings.json` | fünf Subagents mit Verzeichnisgrenzen, Rechte-Allowlist |
| CI / pre-commit | ruff, bandit, gitleaks, detect-private-key |

Die Arbeitspakete WP0–WP7 stehen in `autopilot/tasks.yaml`; die Entscheidungsgrundlage in `docs/stack.md` und `docs/adr/`.

## Lizenz
MIT, © 2026 Stefan Hüllinghorst – siehe LICENSE.
