# API-Vertrag: Production Agent – SSE-Stream und Freigabe

Alle Pfade unterhalb von `http://localhost:8000`.

---

## GET /investigations/stream?line_id=L1&event_id=360

Startet eine Untersuchung und liefert Knotenergebnisse als **Server-Sent Events (SSE)**.
Jedes Event trägt `event:` (Typ) und `data:` (JSON-String). `event_id` (optional, Default 360)
wählt den Replay-Fall; daraus wird die Replay-Uhr `SIM_NOW` für diesen Lauf gesetzt. Der Modus
mock/live steckt im Backend-`LLM_MODE` und wird im `start`-Event nur mitgeteilt, nicht gesetzt.

### Event-Sequenz

```
event: start
data: {"thread_id": "550e8400-e29b-41d4-a716-446655440000", "event_id": 360, "sim_now": "2026-06-15 09:55:00", "line_id": "L1", "mode": "mock"}

event: node
data: {"node": "capture_status", "payload": {"line_status": {"rows": [{"equipment_id": "L1-S1", "packml_state": "Held", "ts": "2026-06-15 09:55:00"}]}, "production_plan": [{"order_id": "A-2207", "planned_qty": 4800, "produced_qty": 3120}], "trace": ["1 Linienstatus und Produktionsplan erfasst"]}, "trace": ["1 Linienstatus und Produktionsplan erfasst"]}

event: node
data: {"node": "analyze_alarms", "payload": {"alarms": [{"alarm_code": "E-4711", "ts": "2026-06-15 09:54:00", "priority": 2}], "alarm_flood": false, "trace": ["1 Linienstatus und Produktionsplan erfasst", "2 Alarme analysiert (1), Alarmflut=False"]}, "trace": ["1 Linienstatus und Produktionsplan erfasst", "2 Alarme analysiert (1), Alarmflut=False"]}

event: node
data: {"node": "retrieve_knowledge", "payload": {"knowledge": [{"chunk_id": "FolienwicklerWartung.md#0", "text": "Folienriss: Folie prüfen und neu einlegen.", "score_bm25": 1.4}, {"event_id": 87, "reason_code": "STO-FOLIE", "duration_min": 18.5}], "trace": ["...", "3 Wissen abgerufen: 1 Dokumente, 1 ähnliche Vorfälle"]}, "trace": ["...", "3 Wissen abgerufen: 1 Dokumente, 1 ähnliche Vorfälle"]}

event: node
data: {"node": "narrow_cause", "payload": {"hypothesis": {"cause": "Folienriss am Folienwickler", "reason_code": "STO-FOLIE", "confidence": 0.82, "evidence": ["E-4711", "EVT-087"], "expected_downtime_min": 20.0}, "trace": ["...", "4 Hypothese: STO-FOLIE (Konfidenz 0.82, Stillstand ~20.0 min)"]}, "trace": ["...", "4 Hypothese: STO-FOLIE (Konfidenz 0.82, Stillstand ~20.0 min)"]}

event: node
data: {"node": "estimate_impact", "payload": {"impact": {"expected_downtime_min": 20.0, "lost_units": 1200, "cost_eur": 4000.0, "orders_at_risk": ["A-2207"]}, "trace": ["...", "5 Wirkung geschätzt: 20.0 min Stillstand"]}, "trace": ["...", "5 Wirkung geschätzt: 20.0 min Stillstand"]}

event: node
data: {"node": "derive_actions", "payload": {"actions": [{"title": "Folie neu einlegen", "description": "Folienrolle am Folienwickler wechseln und neu einlegen.", "level": "approval_required", "confidence": 0.82, "rationale": "E-4711 historisch → STO-FOLIE (EVT-087)", "expected_effect_minutes": null, "policy_notes": []}], "trace": ["...", "6 Maßnahmen abgeleitet, 1 nach Policy"]}, "trace": ["...", "6 Maßnahmen abgeleitet, 1 nach Policy"]}

event: interrupt
data: {"node": "approval_gate", "payload": {"question": "Maßnahmen freigeben?", "actions": [{"title": "Folie neu einlegen", "description": "Folienrolle am Folienwickler wechseln und neu einlegen.", "level": "approval_required", "confidence": 0.82, "rationale": "E-4711 historisch → STO-FOLIE (EVT-087)", "expected_effect_minutes": null, "policy_notes": []}], "impact": {"expected_downtime_min": 20.0, "lost_units": 1200, "cost_eur": 4000.0, "orders_at_risk": ["A-2207"]}, "hypothesis": {"cause": "Folienriss am Folienwickler", "reason_code": "STO-FOLIE", "confidence": 0.82, "evidence": ["E-4711", "EVT-087"], "expected_downtime_min": 20.0}}, "thread_id": "550e8400-e29b-41d4-a716-446655440000"}
```

Der Stream endet nach dem `interrupt`-Event. Der Client hält die `thread_id` vor und sendet nach der Freigabeentscheidung einen POST an `/investigations/approve`.

---

## POST /investigations

Synchroner Start (kein Streaming). Gibt `thread_id` und Interrupt-Payload zurück.

**Request:**
```json
{"line_id": "L1"}
```

**Response:**
```json
{
  "thread_id": "550e8400-e29b-41d4-a716-446655440000",
  "state": {"line_id": "L1", "alarms": [...], "hypothesis": {...}, "actions": [...], "__interrupt__": [...]},
  "interrupt": [{"value": {"question": "Maßnahmen freigeben?", "actions": [...], "impact": {...}, "hypothesis": {...}}}]
}
```

---

## POST /investigations/approve

Gibt Maßnahmen frei oder lehnt sie ab. Setzt den Graphen am `approval_gate`-Knoten fort.

**Request:**
```json
{
  "thread_id": "550e8400-e29b-41d4-a716-446655440000",
  "approved": true,
  "comment": "Folie ist auf Lager, Schlosser wird informiert.",
  "approved_action_titles": ["Folie neu einlegen"]
}
```

**Response:**
```json
{
  "thread_id": "550e8400-e29b-41d4-a716-446655440000",
  "state": {"approval": {"approved": true, "comment": "...", "approved_action_titles": [...]}, "trace": [...]}
}
```

**Fehler 409** – kein wartender Freigabeknoten:
```json
{"detail": "Kein wartender Freigabeknoten für diesen Thread"}
```

---

## GET /investigations/gold/{event_id}

Gold-Wahrheit eines Replay-Falls – **nur für die Eval nach dem Lauf** (reason_hit-Vergleich im
Cockpit). Kein Werkzeug des Agenten: Er sieht das während der Untersuchung nie (ADR-0002). Read-only.

**Response:**
```json
{"event_id": 360, "reason_code": "STO-FOLIE", "duration_min": 10.9, "resolution_action": "...", "cost_eur": 2183.7}
```

**Fehler 404** – Ereignis nicht gefunden.

---

## GET /health

```json
{"ok": true, "model": "claude-sonnet-5", "mode": "mock", "langfuse": false}
```

---

## Invarianten

- Sicherheitsfunktionen (Not-Aus, Schutzkreis) erscheinen **nie** in `actions` (gefiltert durch `action_policy.py`).
- `confidence` in `actions` ist immer ≤ `confidence` in `hypothesis`.
- Der Stream enthält immer genau die Knotenfolge:
  `capture_status → analyze_alarms → retrieve_knowledge → narrow_cause → estimate_impact → derive_actions → (interrupt) approval_gate`.
  Keine Verzweigung (decisions.yaml: „einfachster Graph: keine Verzweigung").
