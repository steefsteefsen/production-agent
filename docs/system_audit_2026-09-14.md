# Systemaudit 2026-09-14

Systematischer Funktionsnachweis mit **vorab definierter Erwartung** je Test, echtem Kommandozeilen-/
Browser-Output als Beleg und PASS/FAIL gegen die Erwartung (nicht gegen „lief durch"). Anlass: das
Ops-Cockpit war durch einen JS-Syntaxfehler komplett unbedienbar, unbemerkt bis zum manuellen Test,
weil :8010 nie einen Browser-Konsolencheck hatte.

Alle Läufe: `LLM_MODE=mock` (kein Live). Browser-Tests: Playwright, 0 Konsolenfehler = Pflicht.

## Ergebnis: 16/16 PASS

| Test | Erwartung | Befehl | Tatsächliches Ergebnis (Auszug) | PASS/FAIL |
|---|---|---|---|---|
| T1 | ruff 0 Fehler | `ruff check .` | **vorher:** `F841 errors_after_load ... ops_check.py:40` → **nachher:** `All checks passed!` | **PASS** (nach Fix) |
| T2 | „X passed, 0 failed" | `pytest -q` (JUnit ausgezählt) | `389 passed, 0 failed, 0 errors, 3 skipped (gesamt 392)`, Exit 0 | **PASS** |
| T3 | Exit 0 UND reason_hit=True | `LLM_MODE=mock python scripts/e2e_replay.py` | `reason_hit: True (STO-FOLIE vs Gold STO-FOLIE)` · `E2E OK` · EXIT=0 | **PASS** |
| T4 | Exit 0 UND Abschluss nach Freigabe | `… e2e_replay.py --decision approve` | `Freigabeknoten erreicht: True` · `Fortsetzung: Freigabe=erteilt, Abschluss=True, Audit-Rolle=schichtleitung` · EXIT=0 | **PASS** |
| T5 | Exit 0 UND sauberer Abbruch + Audit | `… e2e_replay.py --decision reject` | `Fortsetzung: Freigabe=verweigert, Abschluss=True, Audit-Rolle=schichtleitung` · EXIT=0 | **PASS** |
| T6 | zweiter Fall (E2=336) reason_hit=True | `… e2e_replay.py --event-id 336` | `reason_hit: True (STO-ANTRIEB vs Gold STO-ANTRIEB, Dauerfehler 12.7 min)` · EXIT=0 | **PASS** |
| T7 | Judge im Graphen (Aufruf, nicht nur Import) | `grep -n "judge" src/production_agent/graph/workflow.py` | `378: results.append(judge_action(judge_chain, action, evidence))` · `543: g.add_node("check_evidence", …)` · `552/553: add_edge derive_actions→check_evidence→approval_gate` | **PASS** |
| T8 | mind. eine Maßnahme verified=false | Stream mit `tamper_evidence=1` (manipulierter Beleg) über den laufenden Graphen | `Störung nach dokumentiertem Vorgehen … verified=False` · `Betroffene Station … verified=True` · „mind. eine verified=false: True" | **PASS** |
| T9 | Agent-Tab 0 Konsolenfehler | `python scripts/ui_check/agent_check.py` (Playwright :5173) | `Agent-Check · Console-Errors: 0 · Probleme: 0` | **PASS** |
| T10 | erste Karte mit echten Daten, kein „undefined" | Playwright: Karten-Zusammenfassungen auslesen | `Linienstatus erfasst · 2 Aufträge` · `16 Alarme · Alarmflut erkannt` · `Hypothese: STO-FOLIE · Konfidenz 0.80` · `3.320 € Wirkung` · kein „undefined", 10 Karten mit Daten | **PASS** |
| T11 | alle Knoten-Karten (erwartet **8**: 7 Knoten + Freigabe) | Playwright: Kartenlabels zählen | `Karten sichtbar: 8/8 · fehlend=[]` | **PASS** |
| T12 | Freigeben → Abschlusskarte ≤15s | Playwright: Klick Freigeben | `Freigegeben – regulärer Abschluss` erscheint · `T12 … PASS=True` | **PASS** |
| T13 | Ablehnen → Abbruch-Darstellung | Playwright: zweiter Lauf, Klick Ablehnen | `Abgelehnt` erscheint · `T13 … PASS=True` | **PASS** |
| T14 | **Ops-Cockpit 0 Konsolenfehler** | `python scripts/ui_check/ops_check.py` (Playwright :8010) | **vorher:** `SyntaxError: missing : in conditional expression (localhost:8010:265:43)` → `showTab is not defined`; serviert Z265 `actionSyncWP('' + pkg.id + '')` → **nachher:** `Ops-Check · Console-Errors: 0 · Probleme: 0` | **PASS** (nach Fix) |
| T15 | alle 4 Ops-Tabs klickbar, Inhalt sichtbar | `ops_check.py` klickt Ablauf/Stand/Konfiguration/Präsentation | `Screenshots: 5`, alle Panels sichtbar, `Probleme: 0` (Screenshots in docs/demo_walkthrough/ops/) | **PASS** |
| T16 | Präsentation zeigt Scope- UND Stack-Tabelle korrekt | `ops_check.py` prüft iframe-Inhalt | Stack (`Technologie-Entscheidungen` → „keine Behauptung ohne Beleg") und Scope (`Kein ML-Training`) sichtbar, `Probleme: 0` | **PASS** |

## Fixes (vorher → nachher)

- **T14 – Ops-Cockpit JS-Syntaxfehler (Kernbefund).** Ursache: in `autopilot/ops/app.py` (reiner
  Triple-String `_HTML`, kein f-string) kollabiert Python `\'` zu `'`; die inline-`onclick`-Handler
  `actionSyncWP(\'…\')` und drei `getElementById(\'cf-…\')` wurden dadurch zu ungültigem JS
  (Stringliteral-Adjazenz) → der erste Syntaxfehler bricht das ganze `<script>`, alle Handler
  (`showTab`) tot. **Fix:** `actionSyncWP` auf `data-wp`-Attribut + Event-Handler umgestellt (keine
  verschachtelten Quotes mehr); die drei `getElementById`-Stellen von `\'` auf `\\'` korrigiert
  (emittiert valides escaptes Quote). Keine Inhalte geändert.
  Vorher: Console-Errors ≥1 (SyntaxError) · Nachher: `Console-Errors: 0`.
- **T1 – ruff F841.** Ungenutzte Variable `errors_after_load` im neuen `ops_check.py` entfernt.
  Vorher: `Found 1 error` · Nachher: `All checks passed!`.

## Regression verhindern

Zwei dauerhafte Playwright-Konsolenchecks liegen jetzt vor und MÜSSEN künftig bei jeder Änderung an
den generierten HTML-Oberflächen laufen, bevor etwas als „fertig" gilt (nicht nur ruff/pytest/curl):

- `python scripts/ui_check/ops_check.py`  (Ops-Cockpit :8010, 0 Konsolenfehler = Pflicht)
- `python scripts/ui_check/agent_check.py` (Agent-Tab :5173, 0 Konsolenfehler = Pflicht)

Der ausführliche erzählerische Durchlauf bleibt `scripts/demo_walkthrough.py`. Ausführung dokumentiert
in `docs/e2e.md`.
