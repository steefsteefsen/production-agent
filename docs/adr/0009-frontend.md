# ADR-0009: Vite + React + shadcn/ui + Recharts, FastAPI/SSE

Datum: 2026-09-11 · Status: akzeptiert

## Kontext
Ein Cockpit für den Produktionsleiter: ein Panel je Schritt, Drill-down vom Überblick zur Einzelheit, Freigabe-Dialog am Ende.

## Optionen
| Option | Tempo mit Claude Code | Freigabe im UI | Diagramme | Risiko |
|---|---|---|---|---|
| **Vite + React + shadcn/ui + Recharts** | ●●● | ●● eigener Dialog + SSE | ●●● | ●●● niedrig |
| Next.js + CopilotKit (AG-UI) | ●● | ●●● useHumanInTheLoop ↔ interrupt() | ●● | ● Setup |
| Next.js + ECharts | ●● | ●● | ●●● | ●● |
| Streamlit | ●●● | ●● | ●● | ●●● – aber kein React |

## Entscheidung
Vite + React. Anbindung über FastAPI mit SSE (Event je Knoten), Freigabe über /investigations/approve → Command(resume). Demo-Modus ?demo=1 ohne Backend. CopilotKit/AG-UI wäre der Produktionsweg.

## Konsequenzen / Kurzfassung für die Präsentation
„Ein Panel je Schritt, vom Überblick zur Einzelheit; die Freigabe ist ein echter Knoten im Graphen, kein Button-Theater.“ Pflichtpanels bei Zeitnot: 1, 2, 6, 7.

## Quellen (mit Datum)
- CopilotKit Human-in-the-Loop Docs, 2026
- AG-UI-Adoption – marktechpost.com, 21.05.2026
