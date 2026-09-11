# Guardian – der Wächter vor jedem Commit

`autopilot/guardian.py` läuft als `pre-commit`-Hook (installiert durch `make install`) und blockiert den Commit,
wenn eine Regel verletzt ist. Deterministisch, ohne LLM, in Sekunden – damit er *immer* läuft, auch im Autopilot.
Kein Subagent: ein Wächter, den der Builder abschalten oder überreden könnte, wäre keiner.

| Nr | Regel | Was passiert bei Verstoß |
|---|---|---|
| S1 | Keine Secrets, keine `.env` | Commit blockiert |
| S2 | Keine Bibliothek der Ausschlussliste (Databricks, Spark, Kafka, dbt, Airflow, Terraform, Kubernetes, GCP, Iceberg, Delta) | blockiert |
| S3 | MES-Server genau 6 Werkzeuge, RAG genau 1, kein Werkzeug namens *sql/query/write/exec* | blockiert |
| S4 | `schema.sql` und `ALLOWED_TABLES` identisch | blockiert |
| S5 | `decisions.yaml` unverändert (Hash) – Änderung nur mit `GUARDIAN_ALLOW_DECISIONS=1` durch Stefan | blockiert |
| S6 | Sicherheitsmodule geändert → Sicherheits-, Protokoll- und Trajektorientests müssen grün sein | blockiert |
| K1 | Jedes Modul unter `src/` hat seine Testdatei (TEST_MAP) mit mindestens einem als *falsif…* markierten Test | blockiert |
| K2 | ruff und bandit sauber | blockiert |
| D1 | Jedes Modul ist in README oder docs/ namentlich erwähnt | blockiert |
| D2 | Jede ADR hat Kontext / Optionen / Entscheidung / Konsequenzen | blockiert |
| D3 | `src/` geändert ⇒ auch docs/, README oder tests/ geändert | blockiert |
| LLM | `--llm`: Haiku prüft kontextfrei, ob der Diff Aussagen in docs/ veraltet | nur Warnung |

Aufrufe: `make guardian` (manuell), `python autopilot/guardian.py --init` (Hash von decisions.yaml einfrieren, einmal),
`python autopilot/guardian.py --llm` (mit Doku-Konsistenz-Check). Fehlermeldungen tragen die Regelnummer – der
Autopilot spielt sie dem Builder als Nachbesserung zurück.

Was der Guardian **nicht** ist: ein Ersatz für den Reviewer. Der Guardian prüft Form und Invarianten, der Reviewer
prüft Inhalt gegen die Checkliste. Beide zusammen sind das Sicherheitsnetz, bevor irgendetwas als fertig gilt.
