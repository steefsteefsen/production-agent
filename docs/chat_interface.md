# Schnittstelle Chat ↔ Projekt (manuell, drei Dateien)

| Wann | Was ins Projektwissen / in den Chat | Befehl |
|---|---|---|
| Sitzungsbeginn | `STATUS.md` (Stand, offene Entscheidungen, nächste Schritte) – **ersetzt** die alte Version im Projektwissen | `python autopilot/sync.py --status` |
| Nach jedem WP | `autopilot/sync/<WP>.md` – Ziel, Gate, Checkliste, Journal, Reviewer-Urteil, Diff-Stat und die `review_files` des Pakets | `python autopilot/sync.py WP3` |
| Bei Entscheidungsbedarf | `decisions.yaml` (aktuell) + die Frage des Reviewers (steht im Sync-Paket unter „Offene Frage") | – |

Was Claude im Chat **nicht** braucht: Logs (`autopilot/logs/*.log`), den Builder-Verlauf, Diffs in voller Länge. Das Sync-Paket ist bewusst
auf das reduziert, was ein Reviewer sieht – dieselbe Kontextdisziplin wie im Projekt.

## Was pro Schritt gelesen wird (`review_files` in tasks.yaml)
| WP | Reviewer und Chat lesen |
|---|---|
| WP1 | data_layer.md, test_pipeline.py, ADR-0001 |
| WP2a | mes_tools.json, test_mes_tools.py, mes_server.py |
| WP2b | ADR-0004, test_rag.py, Fehlercodes.md |
| WP3 | prompts.py, api.md, test_workflow.py, test_trajectory.py |
| WP4 | rules.py, ADR-0006, test_rules.py |
| WP5 | frontend/README.md, investigation.json, api.md |
| WP6 | evals/report.md, ADR-0007, scenarios.json |
| WP7 | demo_script.md, README.md, CHANGELOG.md |

## Drei Rollen, drei Kontexte
| Rolle | Was sie ist | Kontext | Kann sie der Builder aufrufen? |
|---|---|---|---|
| **Builder** (Subagent) | `claude -p` mit Agent-Datei | CLAUDE.md, decisions.yaml, eigene Verzeichnisse | – |
| **Reviewer** (Review-Gate) | Funktion `reviewer.review()` in run.py, frische Instanz, anderes Modell, nur Read/Grep, JSON-Schema-Urteil | Checkliste, Diff, Tests, review_files – **nicht** der Builder-Verlauf | **Nein** – Trennung der Rollen |
| **Judge** (Eval) | Funktion in `evals/run_evals.py` (agentevals LLM-as-Judge, Haiku) | ein Fall, ein Kriterium, Referenz | **Nein** |

Weder Reviewer noch Judge sind ein MCP-Server: ein MCP-Werkzeug ist etwas, das der Agent *während* seiner Aufgabe
braucht. Wer sich selbst prüfen kann, prüft nicht. Deshalb bleiben beide außerhalb der Reichweite des Builders –
als Funktionen im Orchestrator, mit eigenem, gedropptem Kontext.

## Eskalation
`--review auto` (Standard): Reviewer `pass` → weiter ohne dich. `fail` → ein Nachbesserungslauf mit den beanstandeten
Punkten, dann erneuter Review. `escalate` oder zweites `fail` → Stopp, Frage an dich, Sync-Paket bauen, in den Chat.
