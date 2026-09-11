# Testfälle je Phase – Verifikation (V), Falsifikation (F), Review (R)

Stand des Basisprojekts: **Basis-Testsuite grün** (aktuelle Anzahl siehe README/Statusseite). Neue Fälle je
Arbeitspaket sind Pflicht (Guardian K1) und in `autopilot/tasks.yaml` je Prompt gefordert.

## Phase P/A – Planung, Architektur
| | Test | Datei |
|---|---|---|
| V | Jede Aufgabe in tasks.yaml hat gate, review_gate (≥ 2), review_files | tests/test_plan.py (WP P) |
| F | Aufgabe ohne review_gate → rot | tests/test_plan.py |
| V | Jede ADR hat die vier Pflichtabschnitte | tests/test_adr.py (WP A), Guardian D2 |
| F | ADR mit nur einer Option → rot | tests/test_adr.py |
| R | Scope in einem Satz vortragbar; Ausweichplan konkret | Checkliste |

## Phase WP0/WP1 – Entscheidungen, Daten
| | Test | Datei |
|---|---|---|
| V | Kleine Simulator-DB: 90 Ereignisse, PackML nur Stopp-Zustände, jede Silber-Zeile mit Herkunft | test_simulator.py ✅ |
| F | Anderer Seed ⇒ andere Ereignisse | test_simulator.py ✅ |
| V | Replay-Fälle: Uhr = Start + 5 min, Wahrheit enthält Ursache/Dauer/Maßnahme | test_replay.py ✅ |
| F | Zu wenig Historie ⇒ keine Replay-Fälle (kein stilles Raten) | test_replay.py ✅ |
| V | Rekonstruktion aus Bronze-CSV liefert dieselbe Ereignisanzahl | test_pipeline.py (WP1) |
| F | duration_min ≤ 0 oder reason_code außerhalb Codeliste ⇒ rot | test_pipeline.py (WP1) |
| R | Drei Kennzahlen plausibel; Stichprobe Gold-Beginn = erster Prio-1/2-Alarm | Checkliste |

## Phase WP2a/WP2b – MCP-Server
| | Test | Datei |
|---|---|---|
| V | Über Protokoll: genau sechs Werkzeuge, jede Antwort in `<tool_data trusted="false">` | test_mcp_protocol.py ✅ |
| F | Kein Werkzeug *sql/query/write*; laufende Störung leckt nicht; Zeilenlimit hält und JSON bleibt gültig | test_mcp_protocol.py ✅ (fand den Kürzungs-Bug) |
| V | SQL-Guard: SELECT auf Allowlist geht durch | test_security.py ✅ |
| F | DELETE/DROP/PRAGMA/ATTACH/fremde Tabelle/zweites Statement ⇒ SqlGuardError | test_security.py ✅ |
| V | Injection-Guard: Hülle, Kürzung | test_security.py ✅ |
| F | Instruktionsartige Zeile wird als WARNUNG markiert | test_security.py ✅ |
| V | RRF bevorzugt in beiden Listen Gerankte | test_rag_server.py ✅ |
| F | RRF mit einer Liste dreht nichts um | test_rag_server.py ✅ |
| V | 10 Fehlercode-Queries ⇒ Top-1 ≥ 9 | test_rag.py (WP2b) |
| F | Injection-Dokument markiert; Ergebnis über Limit ⇒ rot | test_rag.py (WP2b) |
| R | Werkzeugbeschreibungen laut lesen; zwei Dokumente lesen | Checkliste |

## Phase WP3/WP4 – Graph, Regeln, Konfidenz
| | Test | Datei |
|---|---|---|
| V | Alarmflut-Trajektorie == Referenz (agentevals strict) | test_trajectory.py ✅ |
| F | Ruhige Linie ohne RAG-Zweig; verbotene Maßnahme nie in der Freigabe; Freigabe immer erreicht, resume beendet | test_trajectory.py ✅ |
| V | Action-Policy: inform / approval_required korrekt gestuft | test_security.py ✅ |
| F | Schutztür/Not-Aus/Interlock (DE+EN) ⇒ verworfen; Konfidenz unter Schwelle ⇒ Hypothesen-Hinweis | test_security.py ✅ |
| V | AI4I-Regeln Positivfall je Modus; Konfidenz == Formel | test_rules.py (WP4) |
| F | Negativfall je Regel; LLM erhöht Konfidenz ⇒ Nachbedingung rot; CBR-Fall mit end_ts > now ⇒ rot | test_rules.py, test_cbr.py (WP4) |
| V | API: /health; Freigabe setzt Graph fort | test_server.py ✅, test_workflow.py ✅ |
| F | Freigabe auf unbekannten Thread ⇒ 409, kein Absturz | test_server.py ✅ |
| R | Systemprompts: Empfehlen ≠ Ausführen, Evidenzpflicht; jede Konfidenz-Zahl erklärbar | Checkliste |

## Phase WP5 – UI
| | Test |
|---|---|
| V | `npm run build`; `?demo=1` füllt alle 7 Panels |
| F | Freigeben ohne thread_id ⇒ Fehlermeldung, kein Absturz; Panel 6 zeigt nie forbidden |
| R | Jedes Panel beantwortet die Frage seines Schritts; Wein-Rot nur bei Freigabe/Prio 1 |

## Phase WP6/WP7 – Eval, Demo
| | Test |
|---|---|
| V | Replay-Eval: Trefferquote, Dauerfehler, Konfusionsmatrix; ein LLM-Judge-Kriterium (Evidenz je Aussage) getrennt ausgewiesen |
| F | Fall mit forbidden-Maßnahme im Fixture ⇒ Eval rot; Konfidenz > Formel ⇒ rot |
| V | make lint test security grün; Demo ≤ 12 min zweimal |
| F | ADR ohne Alternativen ⇒ Skript rot (Guardian D2) |
| R | Zahlen nennen und relativieren können; Ehrlichkeitsgrenzen wörtlich |
