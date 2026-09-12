# Backlog – Phase 2 (Block 9)

Fachliche Erweiterungen nach Abschluss der Kernarbeitspakete WP0–WP7.
Einträge sind keine Versprechen – sie beschreiben den nächsten sinnvollen Schritt,
sobald das Vorgängergate freigegeben ist.

---

## BL-001 · Kausaler Simulator mit drei Stationen

| Feld             | Inhalt |
|------------------|--------|
| **Priorität**    | Hoch |
| **Frühestens nach** | WP7 (Eval-Gate grün) |

### Warum

Der aktuelle Simulator erzeugt Alarme stationsunabhängig.
Für eine glaubwürdige Replay-Eval muss der Agent zwischen der *ersten Station mit Alarm*
und der *Wurzelstation* unterscheiden können – das ist nur möglich, wenn der Simulator
tatsächlich kausal koppelt: Ausfall in Station A → Rückstau in Station B → Sekundäralarm.
Ohne diesen Realismus bewertet die Eval jede Antwort als richtig, die irgendeine Station nennt.

### Umfang

**Drei Stationen** (in Förderrichtung):

| Station          | Kenngröße         | Grenzwert   | Primäralarm          |
|------------------|-------------------|-------------|----------------------|
| Folienwickler    | Folienspannung    | < 3 N       | FOIL_TENSION_LOW     |
| Schneidstation   | Schnittfrequenz   | > 420 /min  | CUTTER_OVERFREQ      |
| Kartonierer      | Staudruck         | > 0,8 bar   | CARTON_JAM           |

Ausbreitungsregeln (hartcodiert, kein LLM):

- Folienriss → Schneidstation verliert Material → CUTTER_OVERFREQ nach ≤ 30 s
- Verschleiß Folienwickler → Spannung sinkt linear bis Grenzwert
- Rückstau Kartonierer → Druck steigt in Schneidstation → sekundärer CUTTER_OVERFREQ

**Drei E2E-Szenarien** (werden als Gold-Replay-Fälle hinterlegt):

| Szenario | Bezeichnung               | Wurzel          | Erwartetes Muster |
|----------|---------------------------|-----------------|-------------------|
| S-01     | Folienriss mit Alarmflut  | Folienwickler   | FOIL zuerst, dann CUTTER |
| S-02     | Verschleiß vor Alarm      | Folienwickler   | AI4I-Verschleißregel als Evidenz, kein vorheriger Alarm |
| S-03     | Rückstau stromabwärts     | Kartonierer     | CARTON zuerst, CUTTER sekundär |

Keine Änderung an `security/`, `sql_guard.py` oder `action_policy.py`.
Der Simulator bleibt deterministisch (seed-gesteuert).

### Akzeptanz

- `pytest tests/replay/test_causal_scenarios.py` grün für S-01, S-02, S-03.
- Die Replay-Eval (WP6) klassifiziert die Wurzelstation korrekt:
  - S-01: Wurzel = Folienwickler (nicht Schneidstation)
  - S-02: Wurzel = Folienwickler, Evidenz = Verschleißregel, kein Alarm als Auslöser
  - S-03: Wurzel = Kartonierer (stromabwärts, obwohl Schneidstation den ersten Folge-Alarm zeigt)
- `ruff check . && pytest -q` bleibt grün.

---

## BL-002 · Playwright-E2E für Szenarien S-01 bis S-03

| Feld             | Inhalt |
|------------------|--------|
| **Priorität**    | Mittel |
| **Frühestens nach** | WP5 (Frontend-Gate grün) und BL-001 abgenommen |

### Warum

Unit- und Replay-Tests prüfen die Logikschicht.
Was sie nicht prüfen: ob der Freigabe-Dialog im Browser korrekt rendert,
ob SSE-Events die UI aktualisieren und ob ein Operator die Empfehlung tatsächlich
bestätigen oder ablehnen kann – genau das ist der kritische Pfad für den PoC-Abnahme-Demo.

### Umfang

- Je Szenario (S-01, S-02, S-03) ein Playwright-Testfall in `tests/e2e/`.
- Jeder Fall startet den Simulator mit dem passenden Seed, wartet auf SSE-Events,
  prüft die angezeigte Empfehlung und klickt Freigeben bzw. Ablehnen durch.
- Kein Mocking des Backends; Playwright läuft gegen den laufenden Dev-Stack
  (`uvicorn` + Vite-Preview).
- Konfiguration über `playwright.config.ts` (baseURL aus Umgebungsvariable).
- CI-Stage: separater Job nach `pytest`, Artefakt: Screenshot bei Fehler.

### Akzeptanz

- `npx playwright test` grün für alle drei Szenarien.
- Screenshot-Artefakte zeigen die korrekte Empfehlung je Szenario.
- Kein neuer Linter-Fehler in `frontend/` und `tests/e2e/`.

---

## BL-003 · Langfuse-Traces als Referenz archivieren

| Feld             | Inhalt |
|------------------|--------|
| **Priorität**    | Niedrig |
| **Frühestens nach** | WP6 (Langfuse-Integration abgenommen) und BL-001 abgenommen |

### Warum

Nach der ersten erfolgreichen Replay-Eval existieren Langfuse-Traces für S-01, S-02 und S-03,
die den Soll-Zustand des Agenten belegen (Werkzeugaufrufe, Konfidenz, Empfehlung, Freigabe).
Diese Traces sind der einzige Nachweis für „der Agent hat richtig entschieden" –
ohne Archivierung gehen sie beim nächsten Langfuse-Reset verloren.

**Kein Code wird geändert.** Es handelt sich ausschließlich um eine Dokumentationsmaßnahme.

### Umfang

- Langfuse-Export (JSON) der drei Trace-IDs ablegen unter `docs/traces/`.
- Dateinamen: `trace_S01_<date>.json`, `trace_S02_<date>.json`, `trace_S03_<date>.json`.
- Eintrag in `docs/AENDERUNGEN.md` (manuell, kein Auto-Marker).
- `docs/traces/README.md` erklärt, wie ein Trace erneut importiert werden kann.
- Keine Änderung an Produktions- oder Testcode.

### Akzeptanz

- Drei JSON-Dateien unter `docs/traces/` committet.
- Jede Datei enthält mindestens: `trace_id`, `input`, `output`, `tool_calls`, `scores`.
- `ruff check . && pytest -q` bleibt grün (kein Code geändert).
- Guardian-Check grün (keine personenbezogenen Daten oder Blocklist-Begriffe in den Traces).
