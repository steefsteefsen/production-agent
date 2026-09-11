# ADR-0008: Claude Sonnet 5 über langchain-anthropic, Context Engineering je Knoten

Datum: 2026-09-11 · Status: akzeptiert

## Kontext
Ein LLM für Ursacheneingrenzung (Knoten 4) und Maßnahmenableitung (Knoten 6) mit strukturierter Ausgabe; Kosten mit eigenem Key; Modellwechsel muss möglich bleiben.

## Optionen
| Option | Werkzeugnutzung | Strukturierte Ausgabe | Kosten | Agnostik |
|---|---|---|---|---|
| **Claude Sonnet 5 (Haiku 4.5 für Routing/Judge)** | ●●● | ●●● | ●●● 2/10 $ je Mio. Token | ●●● via LangChain |
| Claude Opus 5 | ●●● | ●●● | ● 5/25 $ | ●●● |
| Azure OpenAI / Microsoft Foundry | ●●● | ●●● | ●● | ●● Konfigurationswechsel |
| Offenes Modell lokal | ●● | ●● | ●●● | ●●● |

## Entscheidung
Sonnet 5 als Default, Haiku 4.5 für Klassifikation und LLM-as-Judge. Jeder Knoten erhält nur seinen Kontext (kein Vollverlauf) – Context Rot ist belegt. Konfidenz wird nie vom Modell erhöht (Nachbedingung).

## Konsequenzen / Kurzfassung für die Präsentation
„Modellagnostisch über LangChain – heute Claude, morgen Foundry. Context Engineering heißt: jeder Knoten sieht nur, was er braucht.“ Preise vor Nennung an platform.claude.com prüfen.

## Quellen (mit Datum)
- Anthropic Pricing – platform.claude.com/docs/en/about-claude/pricing (Stand 09/2026)
- Context Rot – trychroma.com, 07/2025
- Context Engineering – arXiv 2603.09619
