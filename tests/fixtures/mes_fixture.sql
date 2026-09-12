-- Kontrollierte Mini-DB für tests/test_mes_tools.py
-- sim_now = '2026-06-15 10:00:00'
-- Invarianten:
--   25 historische Gold-Ereignisse (end_ts < sim_now) mit first_alarm_code = 'E-TEST'
--   1  Leck-Ereignis (event_id=99, end_ts > sim_now)  mit first_alarm_code = 'E-LEAK'
--   2  offene + 1 abgeschlossener Auftrag
--   105 aktive Silber-Alarme werden vom Python-Fixture ergänzt (Loop)

INSERT INTO lines VALUES ('L1', 'Testlinie 1', 'Werk Nord', 3600.0, 200.0);

INSERT INTO equipment VALUES
  ('L1-S1', 'L1', 'Folienwickler', 1),
  ('L1-S2', 'L1', 'Siegelstation',  2);

INSERT INTO downtime_reason_codes VALUES
  ('STO-FOLIE',  'Stoerung', 'Folienriss / Folienrolle', 'availability'),
  ('STO-SENSOR', 'Stoerung', 'Sensorfehler / verschmutzt', 'availability');

-- Letzter bekannter Zustand je Betriebsmittel (ts < sim_now)
INSERT INTO equipment_state VALUES
  ('L1-S1', '2026-06-15 09:55:00', 'Held'),
  ('L1-S2', '2026-06-15 09:50:00', 'Execute');

-- 25 historische Gold-Ereignisse – Daten für get_alarm_history (Limit 20)
-- und find_similar_incidents (Limit 5).  Alle end_ts < '2026-06-15 10:00:00'.
INSERT INTO downtime_events_gold
  (event_id, line_id, equipment_id, start_ts, end_ts, duration_min,
   packml_state, reason_code, first_alarm_code, first_alarm_prio,
   alarm_count, alarm_flood, order_id, lost_units, cost_eur, resolution_action)
VALUES
  ( 1,'L1','L1-S1','2026-06-01 08:00:00','2026-06-01 08:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  ( 2,'L1','L1-S1','2026-06-01 20:00:00','2026-06-01 20:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  ( 3,'L1','L1-S1','2026-06-02 08:00:00','2026-06-02 08:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  ( 4,'L1','L1-S1','2026-06-02 20:00:00','2026-06-02 20:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  ( 5,'L1','L1-S1','2026-06-03 08:00:00','2026-06-03 08:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  ( 6,'L1','L1-S1','2026-06-03 20:00:00','2026-06-03 20:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  ( 7,'L1','L1-S1','2026-06-04 08:00:00','2026-06-04 08:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  ( 8,'L1','L1-S1','2026-06-04 20:00:00','2026-06-04 20:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  ( 9,'L1','L1-S1','2026-06-05 08:00:00','2026-06-05 08:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  (10,'L1','L1-S1','2026-06-05 20:00:00','2026-06-05 20:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  (11,'L1','L1-S1','2026-06-06 08:00:00','2026-06-06 08:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  (12,'L1','L1-S1','2026-06-06 20:00:00','2026-06-06 20:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  (13,'L1','L1-S1','2026-06-07 08:00:00','2026-06-07 08:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  (14,'L1','L1-S1','2026-06-07 20:00:00','2026-06-07 20:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  (15,'L1','L1-S1','2026-06-08 08:00:00','2026-06-08 08:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  (16,'L1','L1-S1','2026-06-08 20:00:00','2026-06-08 20:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  (17,'L1','L1-S1','2026-06-09 08:00:00','2026-06-09 08:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  (18,'L1','L1-S1','2026-06-09 20:00:00','2026-06-09 20:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  (19,'L1','L1-S1','2026-06-10 08:00:00','2026-06-10 08:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  (20,'L1','L1-S1','2026-06-10 20:00:00','2026-06-10 20:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  (21,'L1','L1-S1','2026-06-11 08:00:00','2026-06-11 08:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  (22,'L1','L1-S1','2026-06-11 20:00:00','2026-06-11 20:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  (23,'L1','L1-S1','2026-06-12 08:00:00','2026-06-12 08:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  (24,'L1','L1-S1','2026-06-12 20:00:00','2026-06-12 20:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  (25,'L1','L1-S1','2026-06-13 08:00:00','2026-06-13 08:30:00',30.0,'Held','STO-FOLIE','E-TEST',2,3,0,NULL,1800,6000.0,'Folie neu einfaedeln'),
  -- Leck-Ereignis: end_ts > sim_now → darf NICHT in get_alarm_history / find_similar_incidents erscheinen
  (99,'L1','L1-S1','2026-06-15 09:55:00','2026-06-15 10:30:00',35.0,'Held','STO-FOLIE','E-LEAK',2,3,0,NULL,NULL,NULL,NULL);

-- incident_history für alle 25 historischen Ereignisse (LEFT JOIN in find_similar_incidents)
INSERT INTO incident_history
  (incident_id, event_id, summary, root_cause, action_taken, outcome, doc_ref)
VALUES
  ( 1, 1,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  ( 2, 2,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  ( 3, 3,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  ( 4, 4,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  ( 5, 5,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  ( 6, 6,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  ( 7, 7,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  ( 8, 8,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  ( 9, 9,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  (10,10,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  (11,11,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  (12,12,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  (13,13,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  (14,14,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  (15,15,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  (16,16,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  (17,17,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  (18,18,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  (19,19,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  (20,20,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  (21,21,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  (22,22,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  (23,23,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  (24,24,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md'),
  (25,25,'Folienriss Wickler','Folienriss','Folie neu einfaedeln','Wiederanlauf','FolienwicklerWartung.md');

-- Aufträge
-- A-AT-RISK: buffer = (10:20 - 10:00) - (600/3600*60) - 45 = 20 - 10 - 45 = -35 min → gefährdet
-- A-SAFE:    buffer = (12:00 - 10:00) - (600/3600*60) - 45 = 120 - 10 - 45 = +65 min → sicher
-- A-DONE:    produced_qty = planned_qty → erscheint nicht im Produktionsplan
INSERT INTO production_orders VALUES
  ('A-AT-RISK', 'L1', 'Karton 12er', 1200, 600, '2026-06-15 10:20:00', 1),
  ('A-SAFE',    'L1', 'Karton  6er', 1200, 600, '2026-06-15 12:00:00', 3),
  ('A-DONE',    'L1', 'Karton  4er', 1200,1200, '2026-06-15 11:00:00', 2);
