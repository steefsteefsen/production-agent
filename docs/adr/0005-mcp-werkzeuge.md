# ADR-0005: Sechs fachliche MCP-Werkzeuge statt generischem SQL

Datum: 2026-09-11 · Status: akzeptiert

## Kontext
Das LLM braucht Zugriff auf MES-Daten. Generische SQL-MCP-Server existieren fertig; ein eigener Server kostet zwei Stunden.

## Optionen
| Option | Auswahl-Zuverlässigkeit | Sicherheit | Fachsprache | Aufwand |
|---|---|---|---|---|
| **Eigener FastMCP-Server, 6 Werkzeuge** | ●●● | ●●● Read-only/Allowlist/Limit in der Logik | ●●● | ●● |
| Generischer SQLite-MCP | ●● | ● freies SQL | ● | ●●● |
| Generischer Postgres-/DuckDB-MCP | ●● | ● | ● | ●●● |

## Entscheidung
Eigener Server (FastMCP standalone 4.x, stdio). Werkzeuge: get_line_status, get_active_alarms, get_alarm_history, get_production_plan, estimate_impact, find_similar_incidents. Jedes läuft durch sql_guard, injection_guard und audit; jedes filtert auf die Replay-Uhr. Der Guardian erzwingt genau 6 + 1 Werkzeuge (S3).

## Konsequenzen / Kurzfassung für die Präsentation
„Werkzeugauswahl kippt jenseits von 30–50 Tools; sechs klar benannte sind trivial. Read-only und Allowlist gehören in die Fachlogik, nicht in freies SQL.“ Anthropics Tool Search / deferred loading existiert, ist hier unnötig; Anbieter-Benchmarks dazu (88 % vs. 34 %) sind umstritten.

## Ist-Zustand MCP-Aufrufpfad (Doku der Realität, 2026-09-14)
Die MCP-Server sind eigenständig protokollfähig und werden über das Protokoll getestet (In-Memory-`fastmcp.Client` in `tests/test_mcp_protocol.py`). Der **Live-Graph** ruft die Werkzeuge im PoC jedoch aus Latenz- und Robustheitsgründen **in-process** direkt auf (`build_graph`/`_default_tools`), nicht über einen MCP-Subprozess. Grund: `MultiServerMCPClient` (langchain-mcp-adapters 0.3.1) und die installierte `mcp` 2.2.0 sind inkompatibel (`ImportError: RequestContext` aus `mcp.shared.context`); ein kompatibles Versionspaar ist ohne Risiko für die an `mcp` gekoppelte `fastmcp`-Abhängigkeit nicht kurzfristig auflösbar. Echter Protokollbetrieb im Graphen ist damit eine Konfigurations-/Abhängigkeitsänderung nach dem PoC, kein Neubau (der Aufrufpfad ist gekapselt).

## Quellen (mit Datum)
- MCP-Spezifikation 2026-07-28 – blog.modelcontextprotocol.io, 28.07.2026
- Tool-Schwelle – startdebugging.net, 05/2026
- FastMCP vs. MCP Python SDK – agenticwire.news, 2026
