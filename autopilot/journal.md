# Projektjournal – automatisch je Arbeitspaket

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
