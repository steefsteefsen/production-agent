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

## Ist-Zustand MCP-Aufrufpfad (Doku der Realität, aktualisiert 2026-09-14)
Der Live-Graph kann die Werkzeuge über das **echte MCP-Protokoll** laden: `build_tools_from_mcp`
nutzt `fastmcp.Client` und startet die Server `mes` und `maintenance_docs` als eigenständige
**stdio-Subprozesse**; jede Werkzeugausführung ist ein Protokollaufruf. Belegt durch
`LLM_MODE=mock MCP_VIA_PROTOCOL=1 python scripts/e2e_replay.py` (Transport-Log „Starting MCP server
… transport 'stdio'", `reason_hit: True`) sowie `tests/test_mcp_protocol.py` (In-Memory-Protokoll).

Der zuvor genutzte `MultiServerMCPClient` (langchain-mcp-adapters 0.3.1) ist mit `mcp` 2.2.0
inkompatibel (`ImportError: RequestContext` aus `mcp.shared.context`; `mcp` ist an `fastmcp 4.x`
gekoppelt) – er wurde durch den schlanken `fastmcp.Client` ersetzt.

**Standard (Default) ist bewusst weiter In-Process** (`_default_tools`, Schalter
`settings.mcp_via_protocol=False`): schneller und deterministisch für Tests/CI, und die Replay-Uhr
`SIM_NOW` wird pro Untersuchung im Prozess gesetzt. Der Protokollpfad wird per `MCP_VIA_PROTOCOL=1`
aktiviert (dann baut der Graph pro Lauf einen Client mit der passenden `SIM_NOW`). **Offener Punkt:**
den Protokollpfad für die dauerhaft laufende API (einmalig gebauter Graph) mit korrekter
`SIM_NOW`-Propagation pro Request zu verdrahten (Server baut den Graphen je Untersuchung neu) –
geschätzt ein halber Tag nach dem Interview; die Kernmechanik läuft und ist belegt.

## Quellen (mit Datum)
- MCP-Spezifikation 2026-07-28 – blog.modelcontextprotocol.io, 28.07.2026
- Tool-Schwelle – startdebugging.net, 05/2026
- FastMCP vs. MCP Python SDK – agenticwire.news, 2026
