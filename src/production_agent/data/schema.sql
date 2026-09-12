-- Minimal-MES-Schema (Gold-Ebene). Referenzen: ISA-95 Objektmodell, PackML-Zustände (ISA-TR88.00.02).
-- Gold = eine Zeile je STÖRUNGSEREIGNIS (downtime_events_gold), nicht je Alarm.

CREATE TABLE IF NOT EXISTS lines (
  line_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  plant TEXT NOT NULL,
  design_rate_per_hour REAL NOT NULL,        -- Nennleistung
  cost_per_downtime_minute_eur REAL NOT NULL  -- {{DEINE ENTSCHEIDUNG: Kostensatz}}
);

CREATE TABLE IF NOT EXISTS equipment (
  equipment_id TEXT PRIMARY KEY,
  line_id TEXT NOT NULL REFERENCES lines(line_id),
  name TEXT NOT NULL,
  position INTEGER NOT NULL
);

-- PackML: Idle, Starting, Execute, Completing, Complete, Resetting, Holding, Held, Unholding,
-- Suspending, Suspended, Unsuspending, Aborting, Aborted, Clearing, Stopping, Stopped
CREATE TABLE IF NOT EXISTS equipment_state (
  equipment_id TEXT NOT NULL REFERENCES equipment(equipment_id),
  ts TEXT NOT NULL,
  packml_state TEXT NOT NULL,
  PRIMARY KEY (equipment_id, ts)
);

CREATE TABLE IF NOT EXISTS downtime_reason_codes (
  code TEXT PRIMARY KEY,
  category TEXT NOT NULL,     -- z. B. Störung/Rüsten/Material/Organisation (OEE-Verlustquelle)
  description TEXT NOT NULL,
  oee_loss_type TEXT NOT NULL -- availability | performance | quality
);

CREATE TABLE IF NOT EXISTS alarms_silver (
  alarm_id INTEGER PRIMARY KEY,
  equipment_id TEXT NOT NULL REFERENCES equipment(equipment_id),
  ts TEXT NOT NULL,
  alarm_code TEXT NOT NULL,
  priority INTEGER NOT NULL,      -- ISA-18.2: 1 hoch ... 4 niedrig (Verfahren aus decisions.yaml)
  severity INTEGER NOT NULL,      -- OPC-UA-Severity 1..1000 (Herkunft der Priorität)
  sequence_id INTEGER,            -- Alarmsequenz nach Silber-Aggregation
  source_row_id TEXT              -- Herkunft (Bronze) für Nachvollziehbarkeit
);

CREATE TABLE IF NOT EXISTS downtime_events_gold (
  event_id INTEGER PRIMARY KEY,
  line_id TEXT NOT NULL REFERENCES lines(line_id),
  equipment_id TEXT REFERENCES equipment(equipment_id),
  start_ts TEXT NOT NULL,
  end_ts TEXT,
  duration_min REAL,
  packml_state TEXT NOT NULL,     -- Stopped | Held | Suspended | Aborted
  reason_code TEXT REFERENCES downtime_reason_codes(code),
  first_alarm_code TEXT,
  first_alarm_prio INTEGER,       -- Dringlichkeit des Ereignisses (1 = Sicherheit/Anlagenschaden)
  alarm_count INTEGER,
  alarm_flood INTEGER DEFAULT 0,  -- ISA-18.2: >=10 Alarme in 10 min
  order_id TEXT,
  lost_units INTEGER,
  cost_eur REAL,
  resolution_action TEXT          -- was hat geholfen (Basis für find_similar_incidents)
);

-- Kurzstillstände (< kurzstillstand_min, ohne Prio-1): Leistungsverlust, kein Ereignis (ADR-0001)
CREATE TABLE IF NOT EXISTS short_stops (
  station TEXT NOT NULL,
  start_ts TEXT NOT NULL,
  end_ts TEXT NOT NULL,
  duration_min REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS production_orders (
  order_id TEXT PRIMARY KEY,
  line_id TEXT NOT NULL REFERENCES lines(line_id),
  product TEXT NOT NULL,
  planned_qty INTEGER NOT NULL,
  produced_qty INTEGER NOT NULL DEFAULT 0,
  due_ts TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 3
);

CREATE TABLE IF NOT EXISTS incident_history (
  incident_id INTEGER PRIMARY KEY,
  event_id INTEGER REFERENCES downtime_events_gold(event_id),
  summary TEXT NOT NULL,
  root_cause TEXT,
  action_taken TEXT,
  outcome TEXT,
  doc_ref TEXT                    -- Verweis auf Wartungsdokument (RAG)
);

-- AI4I-Sensor-Snapshot je Störungsereignis (Basis für die regelbasierte Ausfallmodus-Prüfung)
CREATE TABLE IF NOT EXISTS ai4i_snapshots (
  event_id INTEGER PRIMARY KEY REFERENCES downtime_events_gold(event_id),
  type TEXT NOT NULL,            -- L | M | H
  air_temp REAL NOT NULL,        -- K
  process_temp REAL NOT NULL,    -- K
  rpm REAL NOT NULL,
  torque REAL NOT NULL,          -- Nm
  tool_wear REAL NOT NULL        -- min
);

-- AI4I-Sensor-Snapshot je Störungsereignis (Wertebereiche des UCI-Datensatzes; Regeln in graph/rules.py)
CREATE TABLE IF NOT EXISTS ai4i_snapshots (
  event_id INTEGER PRIMARY KEY REFERENCES downtime_events_gold(event_id),
  type TEXT NOT NULL,            -- L | M | H
  air_temp REAL NOT NULL,        -- K
  process_temp REAL NOT NULL,    -- K
  rpm REAL NOT NULL,
  torque REAL NOT NULL,          -- Nm
  tool_wear REAL NOT NULL        -- min
);
