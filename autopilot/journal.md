# Projektjournal – automatisch je Arbeitspaket

## 2026-09-12 · WP2a · mcp-agent · ✅

**Was gebaut:** MES-MCP-Server fertiggestellt: 6 Werkzeugdocstrings mit "Nutze dies, wenn…" geschärft; Limits `_MAX_ACTIVE_ALARMS=100 / _MAX_ALARM_HISTORY=20 / _MAX_SIMILAR_INCIDENTS=5` als Konstanten; `estimate_impact` mit vollständiger Pufferformel (`Zeit_bis_due − Restproduktionszeit − Stillstand`), `orders`-Feld und korrektem `orders_at_risk`; `_query` hat `limit`-Parameter als Python-Schutzebene zusätzlich zum SQL-LIMIT; `docs/contracts/mes_tools.json` aktuell.

**Was getestet:** `tests/test_mes_tools.py` – 18 Tests, je Verifikation + Falsifikation für: `<tool_data trusted="false">`-Hülle, Audit-Eintrag, alle 6 Werkzeuge, Limits (100/20/5), Leck-Tests (end_ts > sim_now erscheint nie), genau ein gefährdeter Auftrag (A-AT-RISK), Pufferformel.

**Offen:** –

**Dateien:** src/production_agent/mcp/mes_server.py, docs/contracts/mes_tools.json, tests/fixtures/mes_fixture.sql, tests/test_mes_tools.py

---

## 2026-09-12 11:43 · WP1 · data-agent · ❌ (Versuche 1, 20.4 min, 34 Turns, 1.86786395 USD)
**Agent:** `ruff check . && pytest -q` vollständig grün: 109 Tests bestanden, 94% Coverage (Schwelle 80% erfüllt).

---

**Was gebaut:** `build_from_bronze()` + `_flush_sequence()` in `simulator.py` lesen eine Bronze-CSV (ALPI-Struktur: `machine,timestamp,alarm`) und rekonstruieren Silver-Zeilen mit Sequenz-IDs (Lücke ≤ `gap_min`), Alarmflut-Flag und `source_row_id = "csv:{machine}:{zeile}"` für die Bronze-Herkunft.

**Was getestet:** `tests/test_pipeline.py` mit 20 Tests – je Verifikation + Falsifikation für: Gold ≥ 100 Ereignisse, `duration_min > 0`, gültige `reason_code`s, `alarm_flood ∈ {0,1}`, `source_row_id` in Silver, PackML-Zustände (nur Stopped/Held/Suspended/Aborted), jüngstes Ereignis = E-4711, sowie Sequenzierung/Alarmflut/Ereignisanzahl-Rekonstruktion für `build_from_bronze`.

**Offen:** `docs/data_layer.md` muss nach dem nächsten Commit von `autopilot/status.py --stage` in `docs/index.md` eingetragen werden (D11-Regel des Guardians).

**Dateien:** docs/presentation/index.html, docs/status/index.html, docs/status/status.json, src/production_agent/data/simulator.py

## quota-Pause: quota – warte 15 min, dann erneut (bisher 0/480 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 15 min, dann erneut (bisher 0/480 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 15 min, dann erneut (bisher 0/480 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 15 min, dann erneut (bisher 0/480 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 15 min, dann erneut (bisher 0/480 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 15 min, dann erneut (bisher 0/480 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 15 min, dann erneut (bisher 0/480 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 15 min, dann erneut (bisher 0/480 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 15 min, dann erneut (bisher 0/480 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 15 min, dann erneut (bisher 0/480 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 15 min, dann erneut (bisher 0/480 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte in 15 min (bisher 0/480 min)

## quota-Pause: quota – warte in 1 min (bisher 0/0 min)

## quota-Pause: quota – warte in 1 min (bisher 0/0 min)

## quota-Pause: quota – warte in 1 min (bisher 0/0 min)

## quota-Pause: quota – warte in 1 min (bisher 0/0 min)
## quota-Pause: quota – warte 15 min, dann erneut (bisher 0/480 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 15 min, dann erneut (bisher 0/480 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 15 min, dann erneut (bisher 0/480 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 15 min, dann erneut (bisher 0/480 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 15 min, dann erneut (bisher 0/480 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 15 min, dann erneut (bisher 0/480 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 15 min, dann erneut (bisher 0/480 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 15 min, dann erneut (bisher 0/480 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 15 min, dann erneut (bisher 0/480 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 15 min, dann erneut (bisher 0/480 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 15 min, dann erneut (bisher 0/480 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## 2026-09-12 14:47 · WP2a · mcp-agent · ✅ (Versuche 1, 19.8 min, 59 Turns, 2.506567600000001 USD)
**Agent:** Both `ruff check .` and `pytest` (154 passed, 14 skipped) are green. The commit cannot complete automatically because the pre-commit hooks expect `.venv/bin/python` in `orch-WP2a`, but this worktree has no `.venv` — it uses the `production-agent` venv. 

To unblock the commit, please run once in `orch-WP2a`:
```bash
ln -sf ~/production-agent/.venv .venv
git commit -m "feat(WP2a): MES-MCP-Server fertigstellen"
```

**What was done:**

1. **Docstrings** – all 6 tools have a "Nutze dies, wenn …" sentence from the Produktionsleiter perspective.

2. **Limits** – `_MAX_ACTIVE_ALARMS=100`, `_MAX_ALARM_HISTORY=20`, `_MAX_SIMILAR_INCIDENTS=5` as module constants; each tool passes `limit=` to `_query` so `run_readonly` enforces the cap at the Python layer (the SQL `LIMIT ?` was already there but `run_readonly` wasn't being told the cap).

3. **`estimate_impact`** – complete buffer formula `Puffer = Zeit_bis_due − (Restmenge/rate×60) − expected_downtime_min`; result now includes an `"orders"` list with `buffer_min` and `at_risk` per order, and `"orders_at_risk"` only contains orders with negative buffer.

4. **Replay-Uhr** – all tools already filtered on `ts <= _now(

**Dateien:** autopilot/journal.md, docs/contracts/mes_tools.json, src/production_agent/mcp/mes_server.py, tests/fixtures/mes_fixture.sql, tests/test_mes_tools.py

## quota-Pause: quota – warte 15 min, dann erneut (bisher 0/480 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)

## quota-Pause: quota – warte 0 min, dann erneut (bisher 0/0 min)
