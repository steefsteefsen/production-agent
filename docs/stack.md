# Stack und Entscheidungsgrundlage

Jede Zeile verweist auf eine ADR mit Alternativen, Kriterien und Quellen. Versionen: Stand 11.09.2026, vor Nutzung mit `pip index versions` prüfen.

| Schicht | Wahl | Version (geprüft) | Lizenz | Warum in einem Satz | ADR |
|---|---|---|---|---|---|
| Orchestrierung | LangGraph | ≥ 0.4 | MIT | Graph mit Zustand, Verzweigung und `interrupt()`-Freigabe – der Ablauf ist genau das | 0003 |
| Werkzeuganbindung | MCP über FastMCP (standalone) | 4.0.3 | Apache-2.0 | Sechs fachliche Werkzeuge statt freiem SQL; In-Memory-Client für Protokolltests | 0005 |
| LLM-Zugang | langchain-anthropic → Claude Sonnet 5, Haiku 4.5 für Routing/Judge | – | MIT | Modellagnostisch bleiben; Werkzeugnutzung und strukturierte Ausgabe stark | 0008 |
| Datenschicht | SQLite, Medallion Bronze → Silber → Gold, Replay-Uhr | – | – | Historie und aktueller Fall aus einer Verteilung, Eval fällt gratis ab | 0002 |
| Retrieval | BM25 (rank-bm25) + Qdrant lokal, RRF | – | MIT / Apache-2.0 | Fehlercodes brauchen exakte Treffer, Vektor ergänzt Bedeutung | 0004 |
| Wirkung/Ursache | AI4I-Regeln + Case-Based Reasoning, kein ML-Training | – | CC BY 4.0 (Datensatz) | Transparent, bei 3,4 % Ausfallrate ehrlicher als ein Klassifikator | 0006 |
| Frontend | Vite + React 18 + TypeScript + shadcn/ui + Recharts | – | MIT | Ein Panel je Schritt, schnell generierbar, Freigabe-Dialog | 0009 |
| Observability | Langfuse self-hosted | – | MIT | Tracing je Knoten, lokal, kostenlos; bewusst kein MLOps-Anspruch | 0007 |
| Trajektorien-Tests | agentevals | 0.0.9 | MIT | Vier Match-Modi ohne LLM, LLM-as-Judge optional | test_strategy |
| Sicherheit | sql_guard, injection_guard, action_policy, audit, guardian | – | – | Empfehlen ≠ Ausführen; Daten ≠ Instruktionen; Wächter vor jedem Commit | guardian |

## Standards als Substanz
- **PackML / ISA-TR88.00.02-2022**: 17 Maschinenzustände – eine stehende Linie ist Stopped, Held, Suspended oder Aborted.
- **ISA-18.2 / IEC 62682 / EEMUA 191 (4. Ausg. 2024)**: Alarmflut = ≥ 10 Alarme in 10 Minuten je Bediener.
- **ISA-95 / IEC 62264**: Begriffe des MES-Schemas (Betriebsmittel, Aufträge, Zustände).
- **ISO 13849 / IEC 61508**: Der Agent ist bewusst nicht Teil des sicherheitsgerichteten Steuerungsteils.
- **NIST AI RMF 1.0, EU AI Act (Reg. 2024/1689, Digital Omnibus 2026/1744)**: Governance-Rahmen; Empfehlungsagent mit menschlicher Freigabe ist nicht per se Hochrisiko – Einordnung dokumentiert, kein Rechtsrat.

## Datensätze (nur als Referenz zitiert, Daten im Repo sind simuliert)
- AI4I 2020 Predictive Maintenance, UCI id 601, DOI 10.24432/C5HS5C, CC BY 4.0 – Ausfallmodus-Regeln.
- ALPI – Alarm Logs in Packaging Industry, IEEE DataPort, DOI 10.21227/nfv6-k750 – Struktur der Alarmlogs.
