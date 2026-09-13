# Änderungen (Was / Warum / Alternativen)

Chronologisch, neueste zuerst. Zahlen und Regelbereiche stehen bewusst nicht hier, sondern in den auto-Markern
von README/Doku (sonst veralten sie).

## 2026-09-13 · fix(infra): Headless-Review über Decider statt input()
**Was:** run.py ruft im Nachtlauf (kein TTY) bei Reviewer-'escalate' den Decider (auch ohne --auto-decide): risk≤medium anwenden + Reviewer erneut, risk high → ESCALATION.md + Exit 2, nie input(). --review human/both bricht ohne TTY sauber ab. WP3-Prompt um Stefans Zusatzentscheidungen (Vorfall-ID, RAG-Audit) ergänzt.
**Warum (Problem oder Anlass):** run.py stürzte headless in input("Abnehmen?") mit EOFError ab und blockierte den ganzen Lauf an WP3.
**Alternativen (verworfen, weil ...):** Review im Nachtlauf abschalten – verwirft die unabhängige Kontrolle; blindes Auto-Abnehmen – umgeht die Eskalation bei echten Risiken.
**Auswirkung (Verträge, ADR, Tests):** autopilot/run.py, autopilot/selfcheck.py (neuer Fall), tests/test_run_cli.py (Falsifikation), autopilot/tasks.yaml (WP3).
**Bezug (WP, ADR):** infra/WP3

## 2026-09-13 · docs(P): Nachtlauf-Integration – sechs Pakete nach main
**Was:** WP2b, WP-B, INF-3, INF-4, INF-9, INF-E nach main gemergt; Statusseite, Präsentation und Doku-Marker aufgefrischt; WP3 neu eingereiht.
**Warum (Problem oder Anlass):** Der Nachtlauf hatte die Stränge gebaut, aber die Worktree-Commits/Merges scheiterten still; die Arbeit lag nur auf Rettungs-Branches.
**Alternativen (verworfen, weil ...):** Branches liegen lassen und WP3 zuerst – verworfen, weil abhängige Pakete auf die gemergte Basis warten.
**Auswirkung (Verträge, ADR, Tests):** docs/status/*, docs/presentation/*, README-Marker, orchestrator.json.
**Bezug (WP, ADR):** P

## 2026-09-13 · feat(INF-E): Ops-Cockpit nach main
**Was:** autopilot/ops/app.py – lokale FastAPI-Oberfläche (Port 8010, `make ops`) zum Beobachten/Steuern des Nachtlaufs; drei zur Laufzeit umschaltbare Felder in config/runtime.yaml + Audit, decisions.yaml bleibt read-only.
**Warum (Problem oder Anlass):** Der Nachtlauf brauchte eine lokale Beobachtungs- und Eingriffsoberfläche ohne Antasten von decisions.yaml (Guardian S5).
**Alternativen (verworfen, weil ...):** Direkte CLI-Aufrufe – kein Lanes-Überblick; eigenes React-Frontend – Build-Schritt für lokalen Einzelnutzer unnötig.
**Auswirkung (Verträge, ADR, Tests):** autopilot/ops/app.py, docs/ops.md, Makefile-Ziel ops, tests/test_ops.py, tests/test_mes_coverage.py.
**Bezug (WP, ADR):** INF-E

## 2026-09-13 · docs(INF-9): Backlog und offene Punkte nach main
**Was:** docs/BACKLOG.md mit priorisierten offenen Punkten und Verweisen aus README/Statusseite.
**Warum (Problem oder Anlass):** Offene Entscheidungen und Nice-to-haves waren nur verstreut im Journal dokumentiert.
**Alternativen (verworfen, weil ...):** GitHub-Issues – im öffentlichen PoC-Repo unnötiger Overhead.
**Auswirkung (Verträge, ADR, Tests):** docs/BACKLOG.md, docs/index.md, README-Marker.
**Bezug (WP, ADR):** INF-9

## 2026-09-13 · feat(INF-4): CI/CD-Pipeline und E2E-Smoke nach main
**Was:** GitHub-/GitLab-CI mit E2E-Job (LLM_MODE=mock), Makefile-Ziel e2e, tests/e2e-Smoke, replay-Erweiterung.
**Warum (Problem oder Anlass):** Der PoC brauchte einen reproduzierbaren CI-Lauf ohne API-Schlüssel und einen End-to-End-Rauchtest.
**Alternativen (verworfen, weil ...):** Nur Unit-Tests in CI – deckt das Zusammenspiel UI/Server nicht ab.
**Auswirkung (Verträge, ADR, Tests):** .github/workflows/ci.yml, Makefile, tests/e2e, src/production_agent/data/replay.py.
**Bezug (WP, ADR):** INF-4

## 2026-09-13 · fix(INF-3): Integration von WP2b/WP-B/INF-3 nach main
**Was:** Änderungsprotokoll-Pflicht (D4/D5, changelog_entry) mit den bisherigen Merges vereinigt; journal.commit behält Rückgabe-Prüfung und Rettungs-Commit, ruft zusätzlich changelog_entry.
**Warum (Problem oder Anlass):** Nachtlauf-Rückstand: die gebauten Stränge mussten nach main, dabei kollidierte die neue Begründungspflicht mit der Commit-Prüfung.
**Alternativen (verworfen, weil ...):** INF-3 nur eine Seite übernehmen – verwirft entweder die Rettungs-Commit- oder die Changelog-Logik, beide sind nötig.
**Auswirkung (Verträge, ADR, Tests):** autopilot/journal.py, guardian D4/D5/D10, commit_check.py, tests/test_changelog.py.
**Bezug (WP, ADR):** INF-3

## 2026-09-12 · feat(INF-3): Änderungsprotokoll mit Begründungspflicht eingeführt
**Was:** Änderungsprotokoll mit Begründungspflicht eingeführt (Phase-2 Block 3)
**Warum (Problem oder Anlass):** Bisher fehlte eine strukturierte Begründungspflicht für Änderungen; Entscheidungen waren nicht maschinell prüfbar nachvollziehbar.
**Alternativen (verworfen, weil ...):** Freitext-Kommentare in Commits – verworfen, weil nicht maschinell prüfbar; keine Pflicht – verworfen, weil Entscheidungen undokumentiert bleiben.
**Auswirkung (Verträge, ADR, Tests):** Guardian D4/D5 verschärft (D5 ehemals README-Link → D10); commit_check.py um D5-Check erweitert; journal.py changelog_entry() vor commit(); tests/test_changelog.py neu; alle agent/*.md enden mit Warum-Pflicht.
**Bezug (WP, ADR):** INF-3

## Abo-Betrieb für Claude Code (Max 5×)
**Was:** autopilot/cc.py bündelt den Abo-Betrieb: claude-Subprozesse ohne ANTHROPIC_API_KEY (nur mit
--api-billing mit Key und Budget), Modelle aus settings.env (CC_MODEL_BUILDER/REVIEWER/DECIDER =
sonnet/sonnet/opus), Preflight auf Abo-Login, Quota-Erkennung (429). Eingehängt in run.py, reviewer.py,
decider.py, journal.py und guardian --llm. Der Orchestrator pausiert bei Quota alle Lanes (Prüfung alle
15 min, --quota-wait-hours 8, danach Exit 3) und begrenzt die Parallelität (--max-parallel 3);
Journal-Kosten stehen als „abo". evals/run_evals.py schätzt die Kosten und verlangt --live.
Zusätzlich: die WP-Gates laufen jetzt zuerst über die Abnahmetests und gate_no_skip.
**Warum:** Die Bau-Läufe sollen das Abo nutzen statt die API abzurechnen; nur die Evals kosten bewusst Geld.
**Alternativen:** API-Abrechnung mit Budget-Deckel – verworfen, weil das Fenster teuer würde; ohne
Quota-Pause – verworfen, weil ein leeres Kontingent den ganzen Lauf abbräche.

## Orchestrator, Präsentation, Doku-Index (Block 7/11, Teil B/C)
**Was:** `autopilot/orchestrate.py` (Lane-Scheduler, dauerhafter Zustand `orchestrator.json`, Worktrees, Merge
`--no-ff` mit Guardian und Rollback, Budget, `--dry-run`/`--retry`/`--skip`/`--push`) und `autopilot/plan.yaml`
(Lanes inkl. infra, Abhängigkeiten, Infra-Pakete INF-3/4/9). Journal je WP (`autopilot/journal/<WP>.json`,
`load_all`, `.gitattributes merge=union`); Tag erst nach Merge. `autopilot/present.py` erzeugt
`docs/presentation/index.html` (sechs Tabs, Daten inline, file://-lauffähig) aus git-Log, Journal, Zustand, ADRs,
Coverage. `status.py` erzeugt zusätzlich `docs/index.md` und ruft present im Hook. Guardian K6 (plan⇔tasks,
azyklisch) und D11 (jede docs-Datei im Index). `docs/orchestrator.md`, `architecture.md`, `plan.md`.
**Warum:** Parallel je Lane bauen, ohne dass sich Stränge im Journal überschreiben; der Ablauf soll aus Fakten
erzählt werden statt aus Erinnerung; Doku-Index verhindert verwaiste Dateien.
**Alternativen:** `parallel.sh` – verworfen zugunsten eines Schedulers mit Fortsetzung. Präsentation als Folien von
Hand – verworfen, weil sie veraltet; sie wird aus dem Repo generiert.

## WP0 · Entscheidungen festgeschrieben (decisions.yaml, ADR-0001, BA-01)
**Was:** decisions.yaml als geführte Fachentscheidung (14 reason_codes, sechs Kategorien, Kostensatz 200 €/min,
Konfidenzschwelle 0,60, Rollen/Freigabe, Audit-Pseudonym, Recht/Normen). ADR-0001 (Ereignisdefinition) und
Betriebsanweisung BA-01 (auch als RAG-Kopie in data/docs). Simulator auf decisions.yaml gezogen: alle 14 Codes im
CATALOG, vorgelagerte Anlage UP1 (StateChange, Grund EXT-UP), Kurzstillstände (< kurzstillstand_min ohne Prio-1) in
neue Tabelle short_stops statt Gold, Prio-1 immer Gold, Severity und zwei Prioritätsverfahren (isa18_matrix Standard,
hersteller_severity). Schema: severity in alarms_silver, first_alarm_prio in downtime_events_gold, Tabelle short_stops
(sql_guard-Allowlist ergänzt). Guardian D6 nur bei nicht-leerem Index.
**Warum:** Der Agent entscheidet je Ereignis, nicht je Alarm; die Entscheidungsbasis muss aus Normen abgeleitet und
eingefroren sein, bevor der erste Agentenlauf startet – geraten wäre wertlos.
**Alternativen:** Feste Codeliste im Simulator – verworfen, weil sie von decisions.yaml abweichen kann. Kurzstillstände
in Gold führen – verworfen, weil sie die Ähnlichkeitssuche verwässern (ADR-0001, Option C).

## Doku-Fakten nur aus Markern (Guardian D7 bis D9, K5)
**Was:** README, `docs/guardian.md` und `docs/test_strategy.md` nutzen `<!-- auto:key -->`-Marker; `autopilot/status.py --stage`
füllt sie bei jedem Commit (Hook `status-refresh`, läuft zuerst) aus Fakten (Testanzahl, Coverage, Guardian-Regeln,
Werkzeugzahl, Paketstand, Hooks, letzter Commit). Neue Regeln: D7 (Marker aktuell), D8 (keine getippten Fakten außerhalb
Markern), D9 (Stand-Abschnitt), K5 (pre-commit-`entry` beginnt mit `.venv/bin/python`).
**Warum:** Das README nannte eine veraltete Testanzahl und alte Regelbereiche; handgeschriebene Zahlen veralten still.
**Alternativen:** Handkorrektur – verworfen, weil sie sich wiederholt. LLM-Prüfung im Hook – verworfen wegen Kosten und
Nichtdeterminismus (bleibt manuell über `--llm`).

## Geheimnisse von Konfiguration getrennt (Guardian S7 streng)
**Was:** `settings.env` (committet) hält Konfiguration, `.env` (gitignored) nur noch Geheimnisse (Schlüssel auf
KEY/SECRET/TOKEN/PASSWORD). `config.py` liest `("settings.env", ".env")`, `.env` überschreibt. Guardian S7 verbietet jeden
`.env`-Wert (Länge ≥ acht) in anderen Dateien ohne Ausnahme; S7b prüft die Schlüsselnamen, S7c die `-EXAMPLE`-Endung.
**Warum:** S7 meldete bislang Konfigurationswerte (Modellname, Pfade) als vermeintliches Leck.
**Alternativen:** Schlüsselmuster-Heuristik – verworfen, weil sie die Regel aufweicht. Suffix nur in `.env.example` – verworfen,
weil die echte `.env` die Kollision verursacht.

## Projektstatus als JSON + HTML im Commit-Hook, Coverage-Grenzen (K4)
**Was:** `autopilot/status.py` erzeugt `docs/status/status.json` und `index.html` deterministisch aus tasks.yaml, Journal,
git, Coverage und Guardian; der Hook `status-refresh` schreibt und staged sie. Guardian D6 hält den Stand frisch, K4 setzt
Coverage-Grenzen (pytest-cov, `--cov-fail-under`).
**Warum:** Fortschritt und Zeitstempel sollen aus dem Repo kommen, nicht aus manuellem Einfügen; Coverage soll ein Gate sein.
**Alternativen:** Status nur im Cockpit per Einfügen – verworfen, weil nicht konsistent. Coverage nur in CI – verworfen, weil zu spät.
