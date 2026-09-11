# ADR-0003: Orchestrierung mit LangGraph

Datum: 2026-09-11 · Status: akzeptiert

## Kontext
Der Ablauf hat sieben Schritte mit Zustand, Verzweigung bei Alarmflut, einer Wiederholung bei niedriger Konfidenz und einem Freigabeknoten, an dem ein Mensch entscheidet.

## Optionen
| Option | Graph/Verzweigung | HITL nativ | Checkpointing | MCP | Modellagnostik | Bewertung |
|---|---|---|---|---|---|---|
| **LangGraph** | ●●● | ●●● interrupt()/Command | ●●● SQLite/Postgres | ●●● langchain-mcp-adapters | ●●● | 49/51 |
| Microsoft Agent Framework 1.0 (GA 03.04.2026) | ●●● | ●●● | ●●● | ●●● | ●●● | 46/51 – Azure-nah, schwerer für einen PoC |
| Claude Agent SDK | ● single loop | ●● | ●● | ●●● | ● nur Claude | 33/51 |
| Pydantic AI | ●● | ●● | ● | ●● | ●●● | 33/51 |
| OpenAI Agents SDK | ● | ●● | ● | ●● | ● | 26/51 |
| Temporal-basiert | ●●● | ●● | ●●● durable | ●● | ●●● | Produktionsantwort, nicht PoC |

## Entscheidung
LangGraph. Freigabe über `interrupt()` + `Command(resume)`, Checkpointer SQLite. Für ein Produktivsystem würde Temporal (Durabilität) oder das Microsoft Agent Framework (Azure-Umfeld) evaluiert.

## Konsequenzen / Kurzfassung für die Präsentation
„Mein Ablauf ist ein Graph mit Freigabeknoten – interrupt() und Checkpointer sind genau dieses Primitiv. Alternativen hatten Freigaben, aber die Verzweigungslogik müsste ich selbst schreiben.“ Kosten: Trajektorien-Tests müssen Referenzen pflegen (test_trajectory.py).

## Quellen (mit Datum)
- Microsoft Agent Framework 1.0 GA – techcommunity.microsoft.com, 03.04.2026
- LangGraph Persistence – fast.io, 2026
- Claude Agent SDK Migration Guide – platform.claude.com (Umbenennung 29.09.2025)
