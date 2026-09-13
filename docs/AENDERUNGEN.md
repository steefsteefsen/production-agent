# Änderungen (Was / Warum / Alternativen)

Chronologisch, neueste zuerst. Zahlen und Regelbereiche stehen bewusst nicht hier, sondern in den auto-Markern
von README/Doku (sonst veralten sie).

## 2026-09-13 · feat(WP6): Replay-Eval, Langfuse-Tracing und Observability-ADR
**Was:** `evals/run_evals.py` vom Kostenschätzungs-Skelett zur echten Mock-Eval ausgebaut: wählt die jüngsten Gold-Ereignisse über `replay.select_replay_cases`, lässt je Fall den Graph mit `sim_now` gegen die echten MES/RAG-Werkzeuge laufen (Standard LLM_MODE=mock, `--live` optional für den manuellen Lauf), vergleicht die Vorhersage über `replay.score` mit der Gold-Zeile und prüft deterministisch: Freigabeknoten erreicht, keine forbidden-Maßnahme, Konfidenz ≤ Formel-Obergrenze, Alarmflut→Wissenszweig, Werkzeugreihenfolge. Schreibt `evals/report.md` (Tabelle je Fall, Trefferquote, Ø Dauerfehler, Konfusionsmatrix Ursache) und pflegt `evals/scenarios.json` (Fallauswahl). Neuer optionaler Langfuse-Callback `evals/langfuse_tracing.py` (nur aktiv bei `Settings.langfuse_enabled`, sonst kein Import-Zwang und keine Netzverbindung; Prompt-Version als Trace-Metadatum), `docker-compose.langfuse.yml` (offizieller Self-Host-Stack), Stage `evals` in `.gitlab-ci.yml` (ohne `--live`) und `docs/adr/0007-observability.md`. Verifikations- und Falsifikationstests in `tests/test_run_evals.py` und `tests/test_langfuse_tracing.py`.
**Warum (Problem oder Anlass):** WP6 verlangt einen ehrlichen ersten Berührungspunkt mit MLOps/AIOps: messen statt behaupten (ADR-0002). Das bisherige Eval-Skelett schätzte nur Kosten und erzeugte kein `evals/report.md`; das WP6-Gate blieb offen.
**Alternativen (verworfen, weil ...):** Den Langfuse-Callback direkt in `graph/workflow.py` verdrahten – verworfen, weil er sich in langfuse 4.x sauber über `config={"callbacks": [...]}` von außen injizieren lässt und der Graph-Vertrag so unberührt und offline lauffähig bleibt; die Konfidenzformel voll nachbilden – verschoben, weil im Eval-Kontext nur der Ursachenanteil-Term sauber ableitbar ist, die übrigen Terme werden konservativ als Obergrenze gesetzt (ehrlich im Code dokumentiert).
**Auswirkung (Verträge, ADR, Tests):** Neu/geändert: `evals/run_evals.py`, `evals/langfuse_tracing.py`, `evals/report.md`, `evals/scenarios.json`, `docker-compose.langfuse.yml`, `.gitlab-ci.yml`, `docs/adr/0007-observability.md`, `tests/test_run_evals.py`, `tests/test_langfuse_tracing.py`. Keine Änderung an `decisions.yaml`, `src/` oder bestehenden Verträgen; `replay.py` wird nur genutzt, nicht verändert. WP6-Abnahmetests (`tests/acceptance/test_wp6.py`) laufen jetzt aktiv.
**Bezug (WP, ADR):** WP6/ADR-0007

## 2026-09-13 · feat(WP4): CBR- und AI4I-Regelmodule mit Unit-Tests und ADR-0006
**Was:** Zwei reine, DB-freie Graph-Module aus dem eskalierten Branch `wp/WP4` sauber auf den aktuellen `main` übernommen: `graph/rules.py` (die vier AI4I-Ausfallmodus-Regeln TWF/HDF/PWF/OSF als Funktionen über einen Sensor-Snapshot, Wertebereiche aus decisions.yaml/ADR-0002, inkl. Empty-Snapshot-Schutz: fehlt ein Pflichtschlüssel, liefert die Regel `triggered=False` statt eines Fehltreffers auf Nullwerten) und `graph/cbr.py` (Case-Based Reasoning per Jaccard-Ähnlichkeit über Alarmcodes, PackML-Zustand und Regelmodus, Gewichte aus decisions.yaml). Dazu die Unit-Tests `tests/test_rules.py` und `tests/test_cbr.py` sowie `docs/adr/0006-konfidenzschwelle.md`.
**Warum (Problem oder Anlass):** Der WP4-Branch war acht Commits hinter `main` abgezweigt, löschte das für WP5 benötigte `graph/mock_llm.py` und schrieb `workflow.py`/`server.py` gegen einen alten Stand um – ein `git merge` hätte WP5/WP6 beschädigt. Der algorithmische Kern von WP4 (Regeln + CBR) ist jedoch eigenständig und getestet und kann ohne Risiko für den Demo-Pfad landen.
**Alternativen (verworfen, weil ...):** Ganzen Branch `wp/WP4` mergen – verworfen, weil divergiert und WP5-zerstörend; Regeln/CBR sofort in `workflow.py` verdrahten – verschoben, weil die Graph-Integration gegen den aktuellen `workflow.py` echte Architekturarbeit ist und kurz vor dem Code-Freeze den Demo-Pfad gefährdet.
**Auswirkung (Verträge, ADR, Tests):** Neue Module `src/production_agent/graph/{rules.py,cbr.py}`, neue Tests `tests/test_rules.py` + `tests/test_cbr.py`, neuer `docs/adr/0006-konfidenzschwelle.md`. Keine Änderung an bestehenden Verträgen oder am Graphen; die Verdrahtung in `workflow.py` bleibt bewusst offen (kein `wp/WP4`-Tag).
**Bezug (WP, ADR):** WP4/ADR-0006

## 2026-09-13 · feat(WP5): Agent-Tab – geführte Demo, Funktion und Ausblick je Schritt
**Was:** Der Agent-Tab im React-Cockpit rendert die Untersuchung als sieben Schritt-Karten (je Graph-Knoten) mit Live-Zusammenfassung aus dem SSE-Stream und zwei statischen Annotationen je Knoten – „Funktion" und „Ausblick" (aus einer Quelle: frontend/src/components/demo_annotations.ts). Umschalter „Demo-Notizen" (Präsentation/Produktansicht), Fortschrittsleiste, aufklappbare Details, Freigabe-/Ablehnungskarte über interrupt/Resume, Abschlusskarte mit Audit-Hinweis und Eval (reason_hit) sowie Fehlerbild mit einem Reconnect-Versuch. Reine Stream-Reduktion in frontend/src/components/agentStream.ts. Backend: /investigations/stream nimmt event_id (Default 360) und setzt daraus die Replay-Uhr SIM_NOW, /health meldet den Modus, neuer read-only Endpoint /investigations/gold/{event_id} nur für die Eval nach dem Lauf. Playwright-Smokes (Aufbau + Mock-Durchlauf mit Freigabe), Prüfpfad in docs/e2e.md.
**Warum (Problem oder Anlass):** Für das Interview soll das Cockpit den agentischen Ablauf Schritt für Schritt zeigen und je Knoten erklären, was passiert und wie es nach Kauf ausgebaut würde – ohne die Statusflächen oder andere Tabs zu verändern.
**Alternativen (verworfen, weil ...):** Neue UI-Bibliothek/Stepper-Framework – verworfen, kein neuer Dependency; Annotationen im HTML der Präsentation statt im Cockpit – trennt Erklärung von Funktion; event_id im Cockpit den Modus setzen lassen – Modus bleibt Backend-Sache (nur Anzeige).
**Auswirkung (Verträge, ADR, Tests):** src/production_agent/api/server.py (Stream event_id/SIM_NOW, /health mode, /investigations/gold), frontend/src/components/{Agent.tsx,agentStream.ts,demo_annotations.ts}, tests/e2e/test_ui.py, docs/e2e.md. API-Vertrag erweitert (rückwärtskompatibel: event_id optional, Default 360).
**Bezug (WP, ADR):** WP5/ADR-0002

## 2026-09-13 · fix(orchestrate): Quota-Pausen ins ignorierte Log statt journal.md
**Was:** orchestrate.py schreibt Quota-Pausen jetzt nach autopilot/state/quota.log (per .gitignore ignoriert) statt in die getrackte autopilot/journal.md. journal.md dabei erneut von nachgeschobenen quota-Pause-Zeilen bereinigt.
**Warum (Problem oder Anlass):** Der laufende Orchestrator (Ops-Cockpit) hängte bei API-Quota fortlaufend „## quota-Pause"-Zeilen an die versionierte journal.md an (zuvor 450 Zeilen Log-Müll); sie kamen nach dem Aufräumen sofort zurück. Das ist die Wurzel, nicht das Symptom.
**Alternativen (verworfen, weil ...):** journal.md nur wiederholt bereinigen – der Prozess füllt sie sofort erneut; Ops-Server abschalten – fremder laufender Dienst, nicht eigenmächtig; Zeilen weiter tolerieren – genau das, was aufgeräumt werden soll.
**Auswirkung (Verträge, ADR, Tests):** autopilot/orchestrate.py, autopilot/journal.md; neues ignoriertes Log autopilot/state/quota.log. test_orchestrate.py unverändert grün (prüft Pausier-/Resume-Verhalten, nicht das Schreibziel).
**Bezug (WP, ADR):** Housekeeping/Orchestrator

## 2026-09-13 · chore(status): WP-Stand ehrlich taggen, Journal entrümpeln
**Was:** status.py: der git-Tag wp/<id> ist jetzt die Quelle der Wahrheit für „fertig" (100 %); ein Commit ohne Tag heißt „läuft", nicht mehr „fertig" (behebt Widersprüche wie „fertig bei 30 %"). Tags wp/WP1 und wp/WP5 gesetzt (Abnahmetests test_wp1/test_wp5 grün, Frontend/CI belegt) – WP1 stand fälschlich auf „läuft", WP5 auf „offen"; WP6 steht nun ehrlich auf „läuft" (nur Teil gebaut), WP4/WP7 bleiben „offen" (Kern-Artefakt rules.py bzw. demo_script.md fehlt). Ehrliche Journaleinträge WP1 (Erfolgs-Nachtrag) und WP5 (neu). autopilot/journal.md um 450 „quota-Pause"-Logzeilen bereinigt (1018→121), alle echten WP-Einträge erhalten. tests/test_status.py um zwei Fälle für die neue Tag=fertig-Semantik erweitert.
**Warum (Problem oder Anlass):** Die Statusflächen (README-Stand, Statusseite) waren widersprüchlich/untertrieben: WP5 (Frontend läuft, Playwright grün) und WP1 (Abnahme grün) galten als offen, WP3/WP6 als „fertig" bei niedrigem Prozentwert. Für das Interview soll der Stand kohärent und ehrlich sein.
**Alternativen (verworfen, weil ...):** Deliverable-Erkennung in status.py (Code/Tests statt Tags) – größerer Generator-Umbau, kurz vor dem Interview riskanter; getippte Statuszahlen in der Doku – verboten (D8), veralten; WP4/WP6/WP7 als fertig markieren – unwahr, ihre Kern-Artefakte fehlen.
**Auswirkung (Verträge, ADR, Tests):** autopilot/status.py, autopilot/journal.md, autopilot/journal/WP1.json, autopilot/journal/WP5.json, tests/test_status.py; neue git-Tags wp/WP1, wp/WP5. Regenerierte status.json/index.html/README-Marker/Präsentation. Keine Vertrags-/ADR-Änderung.
**Bezug (WP, ADR):** Housekeeping/Status

## 2026-09-13 · docs(P): Scope-Entscheidungen und Qualitätsgrenzen in Präsentation
**Was:** autopilot/present.py um zwei kuratierte Tabs erweitert: „Scope-Entscheidungen" (Tabelle Abkürzung/Warum/Ausbau nach Kauf) und „Nicht abgekürzt: Sicherheit und Kontrolle" (sql_guard, injection_guard, action_policy, Freigabe-Gate, Audit, Replay-Determinismus). Inhalte als Daten (SCOPE_DECISIONS/QUALITY_GUARANTEES) im Generator, Rendering über eine Tabelle im HTML; tests/test_present.py auf acht Tabs und die neuen Panels erweitert.
**Warum (Problem oder Anlass):** Für das Interview soll die Präsentation ehrlich zeigen, was im PoC bewusst gescoped ist (mit Ausbau-Aufwand) und was gerade nicht abgekürzt wurde – Sicherheit und Kontrolle.
**Alternativen (verworfen, weil ...):** Nur das generierte HTML editieren – verworfen, würde beim nächsten present.py-Lauf überschrieben; freien Fließtext statt Tabelle – schlechter vergleichbar für den Kunden.
**Auswirkung (Verträge, ADR, Tests):** autopilot/present.py, tests/test_present.py, docs/presentation/index.html (generiert). Keine Vertrags-/ADR-Änderung.
**Bezug (WP, ADR):** P/Präsentation

## 2026-09-13 · feat(WP6): Testmatrix, zweiter Fall, Freigabe- und Ablehnungspfad
**Was:** docs/testplan_e2e.md mit Testmatrix (vier Achsen Diagnose/Aktionspfad/Guards/Robustheit, Status-Spalte). scripts/e2e_replay.py um --event-id (Default jüngstes, 360) und --decision none|approve|reject erweitert, run() liefert ein deterministisches Ergebnis-Dict; replay.py um case_for_event_id(). approve/reject setzen nach interrupt() über den SQLite-Checkpointer fort und protokollieren die Entscheidung rollenbasiert im Audit. Neuer E2-Fall 336 (STO-ANTRIEB). tests/test_e2e_replay.py um E2, approve, reject und D1 (drei bitidentische Läufe) ergänzt. CI-e2e-Job: npm ci + Warten auf Vite (5173) vor Playwright; App.tsx erhält data-testid="cockpit".
**Warum (Problem oder Anlass):** Der E2E-Nachweis bestand nur aus einem Fall (STO-FOLIE, 360) und endete am Freigabeknoten; Freigabe/Ablehnung und ein zweiter, andersartiger Fall waren ungeprüft. Die Playwright-E2E scheiterten in CI, weil der Vite-Server ohne npm ci und ohne Readiness-Warten nicht erreichbar war und kein data-testid="cockpit" existierte.
**Alternativen (verworfen, weil ...):** Nur InMemory-Checkpointer für den Resume – verworfen, der Aufgabenrahmen fordert den SQLite-Checkpointer; Playwright gegen den gebauten Build statt Dev-Server – aufwändiger ohne Mehrwert für den Smoke-Test; E2 aus STO-FOLIE wählen – verfehlt die geforderte andere Kategorie.
**Auswirkung (Verträge, ADR, Tests):** scripts/e2e_replay.py, src/production_agent/data/replay.py, tests/test_e2e_replay.py, docs/testplan_e2e.md, .github/workflows/ci.yml, frontend/src/App.tsx. Keine Vertrags-/ADR-Änderung; interrupt/Checkpointer-Verhalten unverändert.
**Bezug (WP, ADR):** WP6/ADR-0002

## 2026-09-13 · fix(ci): setuptools vor pip-audit auf Fix-Version heben
**Was:** Der CI-Schritt „Abhängigkeits-Audit" hebt setuptools vor dem Lauf auf >=83.0.0, dann erst pip-audit.
**Warum (Problem oder Anlass):** pip-audit meldete zwei bekannte CVEs (PYSEC-2026-3447) in setuptools 79.0.1 und brach mit Exit 1 ab; setuptools ist Build-Tool der Runner-Umgebung, keine deklarierte Laufzeit-Abhängigkeit des Projekts.
**Alternativen (verworfen, weil ...):** pip-audit ganz überspringen – verwirft die Prüfung der echten Projekt-Abhängigkeiten; --ignore-vuln PYSEC-2026-3447 – blendet den CVE dauerhaft aus, statt die verwundbare Version zu entfernen.
**Auswirkung (Verträge, ADR, Tests):** .github/workflows/ci.yml (Step „Abhängigkeits-Audit"); keine Verträge/ADR/Tests betroffen.
**Bezug (WP, ADR):** WP7/CI

## 2026-09-13 · fix(config): Knoten 4/6 auf Sonnet, CI-hashFiles je Step
**Was:** Modell-IDs zentral in config.py als ENV-überschreibbare Felder llm_model_main (Knoten 4/6, Default claude-sonnet-5) und llm_model_judge (Judge/Klassifikation, claude-haiku-4-5-20251001); frühere anthropic_model/anthropic_model_fast ersetzt, workflow.py und api/server.py sowie settings.env und docs/contracts/api.md nachgezogen. CI: hashFiles vom Job-if der frontend-Stage auf eine Erkennungs-Step-Ausgabe verschoben, Folge-Steps daran gekoppelt. docs/e2e.md um die Kostenentscheidung ergänzt.
**Warum (Problem oder Anlass):** Opus in den Begründungsknoten ist für die wiederholte Demo zu teuer (ADR-0008 nennt Sonnet als Default); hashFiles ist auf Job-Ebene ungültig (Workspace noch nicht ausgecheckt) und übersprang den frontend-Job stillschweigend.
**Alternativen (verworfen, weil ...):** Opus behalten – zu teuer und gegen ADR-0008; job-if nur entfernen – ließe die npm-Steps ohne Frontend fehlschlagen; decisions.yaml ändern – eingefroren (S5), nur lesen.
**Auswirkung (Verträge, ADR, Tests):** src/production_agent/config.py, graph/workflow.py, api/server.py, settings.env, docs/contracts/api.md, docs/e2e.md, .github/workflows/ci.yml; ADR-0008. Health-Endpunkt liefert nun claude-sonnet-5.
**Bezug (WP, ADR):** ADR-0008

## 2026-09-13 · fix(graph): E2E gegen echte Werkzeuge, Modell-Schalter mock/live
**Was:** _parse löst die <tool_data>-Hülle auf, _extract_packml_state nimmt die stehende Station und {"rows": …}, _top_alarm_codes enthält den Erstalarm (frühester ts), derive_actions stellt Vorfälle vor Dokumente; mes_server._now() liest SIM_NOW aus der Umgebung (kein Leck, ADR-0002). Neu: graph/mock_llm.py, scripts/e2e_replay.py, LLM_MODE (mock/live), build_graph-Schalter, docs/e2e.md, tests/test_e2e_replay.py, Makefile-Ziele e2e-mock/e2e-live, CI-E2E-Schritt.
**Warum (Problem oder Anlass):** Unit-Tests mit Fixture-Werkzeugen (rohes JSON, keine Replay-Uhr) sahen fünf Integrationsfehler nicht; erst der Lauf gegen die echten MCP-Werkzeuge deckte sie auf.
**Alternativen (verworfen, weil ...):** Weiter nur Fixture-Tests – verworfen, weil sie die Hülle, die stehende Station, den Erstalarm und die Replay-Uhr nie berührten.
**Auswirkung (Verträge, ADR, Tests):** src/production_agent/graph/workflow.py, graph/mock_llm.py, graph/prompts.py, mcp/mes_server.py, config.py, settings.env, scripts/e2e_replay.py, tests/test_e2e_replay.py, tests/acceptance/test_wp3.py, .github/workflows/ci.yml, Makefile, docs/e2e.md.
**Bezug (WP, ADR):** WP3/ADR-0002

## 2026-09-13 · docs(P): WP3 integriert – Ermittlungs-Workflow auf main
**Was:** WP3 (LangGraph-Ablauf, LLM-Knoten, SSE, Vorfall-ID-Nachbedingung, RAG-Audit-Test) nach main gemergt; Statusseite/Präsentation/Marker aufgefrischt; WP4/WP5 startbereit.
**Warum (Problem oder Anlass):** WP3 war gebaut und gate-grün, hing aber an der headless-Review-Eskalation; nach dem run.py-Fix und Stefans Zusatzentscheidungen ist es abnahmefähig.
**Alternativen (verworfen, weil ...):** WP3 offen lassen – blockiert WP4–WP7, die alle auf WP3 aufbauen.
**Auswirkung (Verträge, ADR, Tests):** graph/workflow.py, graph/prompts.py, api/server.py, docs/contracts/api.md, tests/acceptance/test_wp3.py, tests/test_workflow.py, tests/test_trajectory.py, tests/test_rag.py.
**Bezug (WP, ADR):** WP3

## 2026-09-13 · fix(infra): Headless-Review über Decider statt input()
**Was:** run.py ruft im Nachtlauf (kein TTY) bei Reviewer-'escalate' den Decider (auch ohne --auto-decide): risk≤medium anwenden + Reviewer erneut, risk high → ESCALATION.md + Exit 2, nie input(). --review human/both bricht ohne TTY sauber ab. WP3-Prompt um Stefans Zusatzentscheidungen (Vorfall-ID, RAG-Audit) ergänzt.
**Warum (Problem oder Anlass):** run.py stürzte headless in input("Abnehmen?") mit EOFError ab und blockierte den ganzen Lauf an WP3.
**Alternativen (verworfen, weil ...):** Review im Nachtlauf abschalten – verwirft die unabhängige Kontrolle; blindes Auto-Abnehmen – umgeht die Eskalation bei echten Risiken.
**Auswirkung (Verträge, ADR, Tests):** autopilot/run.py, autopilot/selfcheck.py (neuer Fall), tests/test_run_cli.py (Falsifikation), autopilot/tasks.yaml (WP3).
**Bezug (WP, ADR):** infra/WP3

## 2026-09-13 · feat(WP3): LangGraph-Ablauf vollständig – 7 Knoten, LLM, SSE, Trajektorien
**Was:** workflow.py von Skelett auf vollständige Implementierung: Knoten 1–7, MCP-Tool-Injektion, build_tools_from_mcp (MultiServerMCPClient stdio); prompts.py mit PROMPT_VERSION; api/server.py SSE-Stream (/investigations/stream) + /investigations/approve; docs/contracts/api.md mit vollständigen Beispiel-Events; config/settings.env auf claude-opus-5 (decisions.yaml-konform) korrigiert; tests/test_workflow.py und tests/test_trajectory.py mit Verifikations-/Falsifikationstests und agentevals-Trajektorienprüfung.
**Warum (Problem oder Anlass):** Das Workflow-Skelett enthielt Platzhalter für LLM-Knoten 4 und 6; build_graph akzeptierte noch keine injizierbaren Tool-Dicts; SSE-Endpunkt fehlte; Modellname wich von decisions.yaml ab.
**Alternativen (verworfen, weil ...):** Verzweigung bei Alarmflut – verworfen (decisions.yaml „einfachster Graph: keine Verzweigung"); Konfidenz-Wiederholung – verworfen (einmal, 60-min-Fenster); FakeListChatModel statt RunnableLambda – aufwändigere Fixture ohne Vorteil.
**Auswirkung (Verträge, ADR, Tests):** docs/contracts/api.md (neu), src/production_agent/graph/prompts.py (neu), api/server.py, workflow.py, state.py, config.py, settings.env; test_workflow.py, test_trajectory.py.
**Bezug (WP, ADR):** WP3

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
