# Externe Quellen: was übernommen wurde, wie und unter welcher Lizenz

Drei Stufen – nie „Repo klonen und anpassen":

| Stufe | Wann | Regel | Beispiele hier |
|---|---|---|---|
| **Abhängigkeit** | Bibliothek löst ein Problem vollständig | pip, Version festgenagelt, `pip-audit` in CI, Lizenz MIT/Apache/BSD | langgraph, fastmcp, agentevals, langfuse, rank-bm25 |
| **Muster** | Ein Repo zeigt ein Vorgehen | Lesen, in ADR zitieren, die 20–50 Zeilen, die man braucht, **selbst schreiben**, Kommentar `# Muster nach <URL>` | NVIDIA Multi-Agent-Intelligent-Warehouse: „LLM schlägt vor, Policy entscheidet, Mensch gibt frei" → action_policy.py + approval_gate |
| **Nie** | Unklare Lizenz (GPL in MIT-Projekt), Fremd-MCP-Server aus Registries, Copy-Paste ganzer Module | – | mcp.so/smithery-Server (Tool-Poisoning-Risiko), OpenShopFloor (verwaist) |

Cherry-Picking von Code aus fremden Repos nur, wenn: Lizenz kompatibel, Datei klein, Ursprung als Kommentar mit Commit-Hash,
Eintrag in dieser Tabelle. Kein `vendor/`-Verzeichnis – was nicht als Abhängigkeit taugt, wird nachgebaut.

## Übernommene Muster
| Was | Woher | Lizenz | Wohin |
|---|---|---|---|
| Propose–Policy–Approve | github.com/NVIDIA-AI-Blueprints/Multi-Agent-Intelligent-Warehouse | Apache-2.0 | security/action_policy.py, graph/workflow.py |
| interrupt()/Command(resume) | LangGraph-Doku | MIT | graph/workflow.py |
| RRF (k=60) | Cormack et al. 2009 / supermemory Guide 04/2026 | – | mcp/rag_server.py |
| AI4I-Ausfallregeln | Matzka 2020, UCI id 601 | CC BY 4.0 | data/simulator.py, graph/rules.py |
| PackML-Zustände | ISA-TR88.00.02 | Standard | schema.sql, UI Panel 1 |
