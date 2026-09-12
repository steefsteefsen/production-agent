# Projektplan – Scope, Budget, Gates

## Scope
Minimalanforderungen: stehende Linie untersuchen, Alarme zu Ereignissen aggregieren, historisches Wissen abrufen,
Wirkung schätzen, sichere Maßnahme empfehlen mit menschlicher Freigabe. Erweiterungen: Freigabe mit Audit,
Replay-Eval, Drill-down-Cockpit, Live-MES.

## Nicht-Scope
Kein ML-Training, kein Feature Store, kein Retraining. Kein Produktivbetrieb, kein Eingriff in die Steuerung. Keine
Fremd-MCP-Server aus Registries. Nicht Databricks/Spark/Kafka/dbt/Airflow/Terraform/Kubernetes/GCP.

## Budget und Lanes
Rund sechzehn Stunden Agentenzeit, verteilt über die Lanes in `autopilot/plan.yaml`. API-Kosten je Replay-Eval mit
Opus höher als mit Sonnet – im Orchestrator-Budget (`--budget-total-usd`) eingerechnet.

## Gates und Review
Jede Aufgabe hat ein automatisches Gate (Exit 0) und ein Review-Gate (Checkliste, `--review`). Der Guardian prüft vor
jedem Commit Sicherheit, Konsistenz und Doku-Aktualität. Abnahmetests je WP sind die unveränderbare Spezifikation.

## Risiken mit Ausweichplan
- Vektorseite (Qdrant/Embeddings) instabil → Rückfall auf BM25 (Retrieval bleibt nutzbar).
- Zeitnot im Cockpit → Panels 3 und 4 zusammenlegen, Pflichtpanels bleiben.
- Live-LLM teuer/langsam → Mock-Modus mit Fixture-Antworten für Tests und Demo.
