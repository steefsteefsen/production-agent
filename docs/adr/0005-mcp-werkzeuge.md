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

## Quellen (mit Datum)
- MCP-Spezifikation 2026-07-28 – blog.modelcontextprotocol.io, 28.07.2026
- Tool-Schwelle – startdebugging.net, 05/2026
- FastMCP vs. MCP Python SDK – agenticwire.news, 2026
