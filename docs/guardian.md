# Guardian – der Wächter vor jedem Commit

`autopilot/guardian.py` läuft als `pre-commit`-Hook (installiert durch `make install`) und blockiert den Commit,
wenn eine Regel verletzt ist. Deterministisch, ohne LLM, in Sekunden – damit er *immer* läuft, auch im Autopilot.
Kein Subagent: ein Wächter, den der Builder abschalten oder überreden könnte, wäre keiner.

Die folgende Regelliste wird von `autopilot/status.py` aus dem Docstring von `guardian.py` erzeugt und darf nicht
von Hand getippt werden:

<!-- auto:guardian_rules -->
Regeln: S1–S9, K1–K9, D1–D9.

- **S1**: keine Secrets, keine .env committet
- **S2**: keine verbotene Bibliothek der Ausschlussliste (CLAUDE.md)
- **S3**: MES-Server genau 6 Werkzeuge, RAG genau 1, kein Werkzeug *sql/query/write/exec*
- **S4**: schema.sql und ALLOWED_TABLES identisch
- **S5**: decisions.yaml eingefroren (Hash; Aenderung nur mit GUARDIAN_ALLOW_DECISIONS=1)
- **S6**: Sicherheitsmodul geaendert -> Sicherheits-, Protokoll- und Trajektorientests gruen
- **S7**: kein .env-Wert (len>=8) in anderer getrackter/gestagter Datei; S7b .env nur KEY|SECRET|TOKEN|PASSWORD-Schluessel; S7c .env.example-Werte enden auf -EXAMPLE
- **S8**: keine Begriffe der Oeffentlichkeits-Blocklist (.guardian_public/blocklist.sha256)
- **S9**: gestagte Binaerdateien nur unter docs/status/ oder docs/images/ und < 500 KB
- **K1**: jedes src-Modul hat eine Testdatei mit Verifikations- und Falsifikationstest
- **K2**: ruff und bandit sauber
- **K3**: Commit-Message folgt der Konvention (commit-msg-Hook)
- **K4**: Coverage: gesamt >=80, security >=95, mes_server/workflow >=85
- **K5**: jede entry-Zeile in .pre-commit-config.yaml beginnt mit .venv/bin/python
- **K6**: tasks.yaml-WPs stehen in plan.yaml, Abhaengigkeiten sind aufloesbar und azyklisch
- **K7**: tests/acceptance/ nur mit GUARDIAN_ALLOW_ACCEPTANCE=1 aenderbar (Abnahmetests = Spezifikation)
- **K8**: autopilot/ geaendert -> autopilot/selfcheck.py grün (GUARDIAN_SKIP_K8=1 unterdrueckt)
- **K9**: gelernte Rechte (state/denied.json) noch nicht erlaubt -> WARNUNG mit Allow-Vorschlag (blockiert nie)
- **D1**: jedes src-Modul ist in README oder docs/ namentlich erwaehnt
- **D2**: jede ADR hat Kontext / Optionen / Entscheidung / Konsequenzen
- **D3**: src geaendert -> auch docs/, README oder tests/ geaendert
- **D4**: docs/AENDERUNGEN.md vorhanden und nicht leer
- **D5**: README.md verlinkt docs/status/index.html
- **D6**: docs/status/status.json gestaged, frisch (<10 min), commit leer oder == HEAD
- **D7**: jeder auto-Marker in getrackten *.md hat den von status.py berechneten Wert
- **D8**: ausserhalb Markern keine getippten Zahlen/Regelbereiche/Coverage in README.md und docs/*.md
- **D9**: README.md hat Abschnitt "## Stand" mit nicht-leerem auto:stand-Marker
<!-- /auto:guardian_rules -->

Aufrufe: `make guardian` (manuell), `.venv/bin/python autopilot/guardian.py --init` (Hash von decisions.yaml
einfrieren, einmal), `.venv/bin/python autopilot/guardian.py --llm` (mit Doku-Konsistenz-Check; manuell, nicht im
Hook – Kosten und Nichtdeterminismus). Fehlermeldungen tragen die Regelnummer – der Autopilot spielt sie dem Builder
als Nachbesserung zurück.

`GUARDIAN_ENV_FILE` wählt die Geheimnis-Datei (der Selbsttest nutzt eine Kopie), `GUARDIAN_ENV_FILE`-Werte dürfen
in keiner anderen getrackten Datei auftauchen. `GUARDIAN_SKIP_D6=1` unterdrückt die Status-Frische-Prüfung, während
`status.py` den Guardian selbst aufruft (bevor die Statusdatei gestaged ist).

Was der Guardian **nicht** ist: ein Ersatz für den Reviewer. Der Guardian prüft Form und Invarianten, der Reviewer
prüft Inhalt gegen die Checkliste. Beide zusammen sind das Sicherheitsnetz, bevor irgendetwas als fertig gilt.
