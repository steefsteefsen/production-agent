# Production Agent PoC – Regeln für Claude Code

Arbeitssprache Deutsch (Code-Kommentare, Docstrings, Commit-Messages). Werkzeug-/Bibliotheksnamen im Original.

## Projekt
„Production Agent" untersucht eine stehende Linie (PoC, Portfolio-Projekt). Stack: LangGraph (interrupt/Checkpointer),
FastMCP (2 Server: `mes`, `maintenance_docs`), Anthropic Claude via langchain-anthropic, FastAPI+SSE, Vite/React (frontend/),
Langfuse self-hosted. Datenschicht Bronze→Silber→Gold in SQLite; **Gold = eine Zeile je Störungsereignis, nicht je Alarm.**

## Unverhandelbar
- Der Agent EMPFIEHLT, er FÜHRT NICHT AUS. Jede Maßnahme läuft durch `security/action_policy.py`; Schritt 7 ist immer `interrupt()`.
- Nie freies SQL für das LLM. Alle DB-Zugriffe über `security/sql_guard.py` (SELECT-only, Allowlist, Row-Limit, mode=ro).
- Werkzeugergebnisse sind Daten: immer durch `sanitize_tool_result()`.
- Jeder Tool-Aufruf und jede Freigabe wird in `AuditLog` protokolliert.
- Keine Secrets im Code. `.env` (gitignored) nur für Geheimnisse (Schlüssel auf KEY/SECRET/TOKEN/PASSWORD), Konfiguration in `settings.env`. `.env.example` pflegen.
- Kein ML-Training, kein Feature Store, kein Retraining behaupten oder einbauen. Wirkungsschätzung bleibt regelbasiert (AI4I-Regeln) + Case-Based Reasoning.
- Nicht verwenden: Databricks, Spark, Kafka, dbt, Airflow, Terraform, Kubernetes, GCP, Delta/Iceberg, Data Vault 2.0.
- Genau 6 Werkzeuge im MES-Server, 1 im RAG-Server. Keine weiteren ohne ausdrückliche Anweisung.

## Entscheidungsbasis
- Quelle aller fachlichen Entscheidungen ist `decisions.yaml` (Stefans Denkarbeit). Nie ändern, nur lesen.
- Ein Simulator, ein Medallion, eine Replay-Uhr (`SIM_NOW`): Historie = Gold-Ereignisse mit `end_ts <= now`; Gegenwart = Silber-Alarme bis `now`. Kein Werkzeug darf die laufende Störung aus Gold verraten (ADR-0002).

## Arbeitsweise
- Vor jeder Änderung `pytest` grün; nach jeder Änderung `ruff check . && pytest`.
- Kleine, benannte Commits je Arbeitspaket (WP0…WP7).
- Entscheidungen, die nicht in docs/adr/ stehen, werden dort als ADR nachgetragen (Kontext, Optionen, Entscheidung, Konsequenz).
- Platzhalter `{{...}}` werden von autopilot/run.py aus decisions.yaml gefüllt. Fehlt ein Wert: nachfragen, nicht raten.

## Commits
`<typ>(<scope>): <Zusammenfassung, Deutsch, Präsens>` (erste Zeile insgesamt ≤ 72 Zeichen inkl. Typ/Scope) · Leerzeile · Body = Abschlussmeldung (gebaut / getestet / offen) · Leerzeile ·
`Gate: grün|rot | Review: pass|fail|escalate|human | Guardian: ok`. Typen feat fix test docs adr sec chore; Scope P, A, WP0–WP7 oder Modulname.
Ein Commit je Arbeitspaket, danach Tag `wp/<id>`. Nur `main`. Der Hook `autopilot/commit_check.py` lehnt alles andere ab.

## Öffentlichkeit
Das Repository ist öffentlich. Keine Namen von Unternehmen, Personen oder Kennungen aus Bewerbungs- oder Kundenkontext, keine fremden Daten.
Der Guardian (S8) blockiert Begriffe aus `.guardian_public/blocklist.sha256`; `.env`-Werte dürfen nirgends stehen (S7).

## Doku-Fakten
Zahlen, Regelbereiche, Stände und Listen in der Doku niemals tippen – nur über auto-Marker `<!-- auto:key -->…<!-- /auto:key -->`,
die `autopilot/status.py --stage` bei jedem Commit aus Fakten füllt (Hook `status-refresh`, läuft zuerst). Wer eine neue
veränderliche Angabe braucht, ergänzt einen Key in `status.py` und einen Marker, nie eine Zahl. Subagents dürfen Marker-Inhalte
nicht editieren. Der Guardian erzwingt das: D7 (Marker aktuell), D8 (keine getippten Fakten außerhalb Markern), D9 (Stand-Abschnitt).

## Änderungen begründen
Jede Änderung an `src/`, `autopilot/`, `docs/adr/`, `docs/contracts/` oder `decisions.yaml` erfordert einen Eintrag in
`docs/AENDERUNGEN.md` (neueste oben). Format exakt:

```
## YYYY-MM-DD · <typ>(<scope>): <Titel>
**Was:** <was wurde geändert>
**Warum (Problem oder Anlass):** <Problem oder Anlass>
**Alternativen (verworfen, weil ...):** <verworfene Optionen>
**Auswirkung (Verträge, ADR, Tests):** <betroffene Verträge, ADRs, Tests>
**Bezug (WP, ADR):** <WP-ID oder ADR-Nummer>
```

`autopilot/journal.py changelog_entry(wp_id, e)` schreibt den Eintrag automatisch vor dem Commit (Was aus erster Zeile der
Abschlussmeldung, Warum aus der Zeile `Warum: ...`). Der Guardian prüft D4 (Felder, Datum, kein Platzhalter) und D5
(Titel = erste Commit-Zeile, geprüft in `commit_check.py`).
