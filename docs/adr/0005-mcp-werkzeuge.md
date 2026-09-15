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

**Demo-Default ist IN-PROCESS** (`_default_tools`; `api/server.py` liest `MCP_VIA_PROTOCOL`, Default
`0`). Grund, am 2026-09-16 im Browser live reproduziert (Audit N-1): Die dauerhaft laufende API baut
den Graphen EINMALIG beim Import. Im Protokollpfad werden dabei die stdio-Subprozesse gespawnt und
ihr `os.environ` friert ein. Die Replay-Uhr `SIM_NOW` ist aber erst je Request bekannt und wird nur
im Parent-Prozess gesetzt – ein laufender Subprozess sieht das nie und fragt zur ECHTEN Zeit ab.
Folge im echten Demo-Pfad (Ereignis 360): `0 ähnliche Vorfälle`, Ursache `STO-UNBEKANNT`, beide
Maßnahmen vom Judge abgelehnt. In-Process liest `SIM_NOW` im selben Prozess je Aufruf frisch →
korrekte Replay-Zeit (5 Vorfälle, `STO-FOLIE`, Judge bestätigt).

**Der Protokollpfad bleibt OPT-IN** (`MCP_VIA_PROTOCOL=1`) und funktioniert, wenn `SIM_NOW` VOR dem
Bau des Graphen feststeht (Einzelfall, z. B. `LLM_MODE=mock MCP_VIA_PROTOCOL=1 python
scripts/e2e_replay.py`: `SIM_NOW` wird beim Prozessstart gesetzt, der Subprozess erbt es). Für die
interaktive Demo mit wechselnden Ereignissen ist das nicht anwendbar. **Robuste Lösung (Backlog,
nach dem Interview):** `SIM_NOW` je Werkzeugaufruf als Argument durch den Graphen reichen (statt über
die Prozess-Umgebung); das entkoppelt die Replay-Uhr vom Subprozess-Spawn (~halber Tag). Bis dahin
ist In-Process der korrekte, belegte Demo-Default.

## Quellen (mit Datum)
- MCP-Spezifikation 2026-07-28 – blog.modelcontextprotocol.io, 28.07.2026
- Tool-Schwelle – startdebugging.net, 05/2026
- FastMCP vs. MCP Python SDK – agenticwire.news, 2026
