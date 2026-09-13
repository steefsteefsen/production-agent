# ADR-0007: Observability über Langfuse (self-hosted)

Datum: 2026-09-13 · Status: akzeptiert

## Kontext
Der Agent trifft in sieben Knoten Entscheidungen und ruft Werkzeuge auf. Für Nachvollziehbarkeit
(EU-AI-Act Art. 13 – Transparenz), Fehlersuche und die Interview-Demo braucht es eine Sicht darauf,
was ein Lauf tat: welche Knoten, welche Werkzeuge, welche Latenzen, welche Prompt-Version. Das ist
Observability, kein Modellbetrieb.

## Was es ist – und was NICHT
Tracing zeigt **Läufe als Traces, Knoten als Spans, Werkzeug-/LLM-Aufrufe als Child-Spans**, mit
`PROMPT_VERSION` als Metadatum. Es ist **kein Drift-Monitoring**, **kein Retraining**, **kein
Feature Store** und **keine automatische Qualitätsbewertung**. Die Eval-Zahlen (Trefferquote,
Dauerfehler) kommen aus dem Replay (ADR-0002), nicht aus dem Tracing. Bewusst MLOps-light: ein
ehrlicher erster Berührungspunkt mit AIOps, nicht mehr.

## Optionen

| Option | Was es ist | Vorteil | Nachteil |
|---|---|---|---|
| **Langfuse self-hosted (gewählt)** | Open-Source-Tracing für LLM-Anwendungen, Docker-Compose, langchain-Callback | self-hostbar (keine Daten außer Haus), LangChain/LangGraph-Integration, Prompt-Versionierung, offenes Lizenzmodell | eigener Stack (Postgres/ClickHouse/Redis/MinIO) zu betreiben |
| LangSmith | gehostetes Tracing/Eval von LangChain | nahtlos, wenig Setup | SaaS, Daten außer Haus, an einen Anbieter gebunden |
| Arize Phoenix | OpenTelemetry-basiertes LLM-Tracing/Eval | offen, OTel-Standard, gute Eval-Bausteine | Fokus stärker auf Eval/Embeddings-Drift; für diesen PoC mehr als nötig |

## Entscheidung
Langfuse self-hosted. Der Callback wird **außerhalb** des Graph-Codes injiziert
(`evals/langfuse_tracing.py` → `config={"callbacks": [...]}`), damit der Graph ohne Langfuse
unverändert und ohne Netzverbindung läuft. Aktiv nur bei gesetzten Keys
(`Settings.langfuse_enabled`). Compose in `docker-compose.langfuse.yml`.

## Konsequenzen
- Ohne Keys: kein Callback, kein Import-Zwang, keine Netzverbindung – Tests/Eval/API laufen normal.
- Mit Keys: sieben Spans je Lauf, Werkzeuge als Kinder, Prompt-Version am Trace.
- Grenze: Tracing beweist keine Qualität. Die Aussage über Trefferquote bleibt beim Replay und ist
  eine Obergrenze (der Simulator kennt seine Ursachen).
