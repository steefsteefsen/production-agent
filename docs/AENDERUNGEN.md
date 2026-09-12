# Änderungen (Was / Warum / Alternativen)

Chronologisch, neueste zuerst. Zahlen und Regelbereiche stehen bewusst nicht hier, sondern in den auto-Markern
von README/Doku (sonst veralten sie).

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
