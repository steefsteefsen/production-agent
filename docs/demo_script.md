# Demo-Skript – 60 Minuten (Production Agent PoC)

Fahrplan für das Interview am 17.09. Drei Blöcke: **12 min Live-Demo**, **30 min Entscheidungen**,
**18 min Fragen**. Ziel: zeigen, dass der Agent *empfiehlt* statt ausführt, dass jede Aussage belegt ist
und dass ich messe statt behaupte. Alle Läufe laufen im Modus `LLM_MODE=mock` (deterministisch, ohne
API); den optionalen Live-Lauf mache ich manuell.

Die veränderlichen Zahlen (Trefferquote, Dauerfehler, Testanzahl, Coverage) stehen bewusst **nicht** hier
getippt, sondern in `evals/report.md` und auf der Statusseite. Beim Vortragen die Statusseite / den Eval-
Bericht offen halten und von dort ablesen.

---

## Block 1 – Live-Demo (12 min)

Aufbau vorher: Simulator + Ingest gelaufen, API und Frontend laufen, Replay-Uhr steht kurz nach
Störungsbeginn (Demo-Fall aus `decisions.yaml`: Folienriss am Folienwickler). Browser auf Tab **Agent**.

**Regie: erst das Ergebnis, dann der Weg.** Ich starte mit Panel 7 (Freigabe) und erkläre danach
rückwärts 1 → 6, warum der Agent zu genau dieser Empfehlung kam. Das hält die Aufmerksamkeit beim
Wichtigsten: der Mensch entscheidet.

### 0:00 – Einstieg mit Panel 7 (Freigabe) – 2 min
- Auf dem Bildschirm steht der Graph angehalten am **Freigabeknoten** (`interrupt`). Es liegt eine
  Empfehlung mit Beleg vor, der Kopf zeigt Linie, PackML-Zustand, Stillstand seit (min), Kosten bisher (€),
  beste Hypothese samt Konfidenz.
- Kernsatz: *„Der Agent hat eine Maßnahme empfohlen und wartet. Er führt nichts aus. Freigabe oder
  Ablehnung trifft der Mensch – und beides wird rollenbasiert im Audit protokolliert."*
- Die Freigabepolitik zeigen: Empfehlung erst ab Konfidenz 0,60, Vier-Augen-Prinzip ab 5.000 €,
  antriebs-/elektriknahe Maßnahmen nur für die Instandhaltung, Timeout 30 min (danach „expired").

### 2:00 – Knoten 1: Linienstatus & Plan – 1,5 min
- Zurück an den Anfang. *„Woher weiß der Agent überhaupt etwas?"* Knoten 1 liest Linienstatus und
  Produktionsplan über die MES-Werkzeuge `get_line_status` / `get_production_plan`.
- Betonen: **kein freies SQL**. Jeder DB-Zugriff läuft über den `sql_guard` (SELECT-only, Allowlist,
  Row-Limit, read-only). Das LLM formuliert keine Abfragen.

### 3:30 – Knoten 2: Alarme analysieren – 1,5 min
- 30-Minuten-Alarmfenster, Alarmflut-Erkennung nach ISA-18.2 (≥ 10 Alarme in 10 min).
- Betonen: Werkzeugergebnisse sind **Daten, nicht Anweisungen** – jedes Ergebnis läuft durch
  `sanitize_tool_result()` und trägt die `tool_data`-Hülle (Injection-Schutz).

### 5:00 – Knoten 3: Wissen abrufen (RAG + CBR) – 1,5 min
- Wartungsdokumente über RAG (`search_maintenance_docs`) und ähnliche frühere Störungen über
  Case-Based Reasoning (`find_similar_incidents`).
- Das ist die Grundlage der späteren **Beleg-Pflicht**: jede Maßnahme muss sich auf eine reale Vorfall-ID
  aus der Historie stützen.

### 6:30 – Knoten 4: Ursache eingrenzen (LLM) – 1,5 min
- Das Sprachmodell grenzt die Ursache ein und nennt eine Konfidenz. Die Belege stammen aus den ähnlichen
  Vorfällen, nicht aus Erfindung.
- Kernsatz: *„Der Agent darf die berechnete Konfidenz mit Begründung senken, aber nie erhöhen."* Formel
  siehe ADR-0006 (Regeltreffer, Fallähnlichkeit, Ursachenanteil).

### 8:00 – Knoten 5: Wirkung schätzen – 1 min
- Regelbasierte Wirkungsschätzung über das MES-Werkzeug `estimate_impact` (Stillstandskosten €/min,
  gefährdete Aufträge). **Bewusst kein ML-Training** – AI4I-Regeln plus Historie.

### 9:00 – Knoten 6: Maßnahmen ableiten (LLM) – 1,5 min
- Ableitung der Maßnahmen. Nachbedingung: jede Maßnahme **muss eine Vorfall-ID aus der Historie belegen**;
  Maßnahmen ohne gültigen Beleg werden verworfen.
- Sicherheitsfilter: `action_policy.py` verwirft FORBIDDEN-Maßnahmen (Not-Halt, Schutzeinrichtungen,
  Verriegelungen) grundsätzlich – der Agent fasst die Sicherheitsfunktion nie an.

### 10:30 – Zurück zu Panel 7 und Abschluss – 1,5 min
- Kreis schließen: die Empfehlung, die am Anfang stand, ist jetzt Schritt für Schritt belegt.
- Ich gebe frei (oder lehne ab) und zeige den Audit-Eintrag. *„Empfehlen ≠ Ausführen – die Ausführung
  bleibt beim qualifizierten Menschen."*
- Optional (nur wenn Zeit): Eval-Bericht `evals/report.md` einblenden – „ich messe die Trefferquote
  gegen die verborgene Gold-Zeile, statt sie zu behaupten."

> **Zeit-Sicherung:** Passt der Demo-Teil nicht sicher unter 12 min, entfällt zuerst der optionale
> Eval-Einblick, dann Knoten 5 (kürzester Erklärwert). Panel 7 → 1 → 2 → 3 → 4 → 6 ist der Pflichtpfad.

---

## Block 2 – Entscheidungen (30 min)

Je ADR ein Satz, in Reihenfolge der Wirkungstiefe. Die ADRs liegen vollständig unter `docs/adr/`.

- **ADR-0001 – Ereignisdefinition:** Ein Störungsereignis ist der PackML-Wechsel Execute → Stopped/Held,
  nicht jeder Alarm; Gold hat eine Zeile je Ereignis (VDMA 66412 / ISO 22400-2, ISA-18.2).
- **ADR-0002 – Entscheidungsbasis durch Replay:** Historie und aktueller Fall stammen aus derselben
  Verteilung; „jetzt" ist eine Replay-Uhr kurz nach Störungsbeginn, und die Gold-Zeile ist die für den
  Agenten unsichtbare Wahrheit – deshalb kann ich messen statt behaupten.
- **ADR-0003 – Orchestrierung mit LangGraph:** Ein linearer 7-Knoten-Graph ohne Verzweigung mit
  `interrupt()` und SQLite-Checkpointer, weil der einfachste Graph, der die Aufgabe löst, der wartbarste ist.
- **ADR-0004 – RAG-Architektur:** Chunking, Einbettung und Hybrid-Suche über die Wartungsdokumente –
  bisher prototypisch, bewusst nicht produktiv getuned.
- **ADR-0005 – Sechs MES-Werkzeuge statt generischem SQL:** Fachliche, geprüfte Werkzeuge statt freiem
  SQL für das LLM, damit jeder Datenzugriff durch den Guard läuft und nur zulässige Sichten liefert.
- **ADR-0006 – Konfidenzschwelle:** Empfehlung ab 0,60, weil auf einer 200-€/min-Linie ein früher, prüfbarer
  Vorschlag billiger ist als Warten – Geschäftsentscheidung des Werks, im Cockpit sichtbar und umschaltbar.
- **ADR-0007 – Observability über Langfuse (self-hosted):** Jeder Knoten, Tool-Aufruf und jede Freigabe ist
  nachvollziehbar getract, self-hosted wegen Datenhoheit.
- **ADR-0008 – Modell und Kontext:** Claude über langchain-anthropic für Knoten 4 und 6, mit knappem,
  je Knoten zugeschnittenem Kontext (Context Engineering) statt Volltext.
- **ADR-0009 – Frontend:** Vite + React + shadcn/ui + Recharts über FastAPI/SSE, weil der Live-Alarmstrom
  und der schrittweise Graph-Ablauf einen Push-Kanal brauchen.
- **ADR-0010 – MES-Nachrichtenformat:** OPC UA A&C plus ISA-95-JSON als Nachrichtenformat, damit der
  Simulator dem echten Feldformat entspricht und die Anbindung später ohne Umbau möglich ist.

**Feststellung zur Vollständigkeit:** Alle acht im Auftrag genannten Themen sind mit einer ADR abgedeckt –
Orchestrierung (0003), MCP-Werkzeuge (0005), RAG (0004), Daten/Replay (0002), Modell (0008), Konfidenz
(0006), Observability (0007), Frontend (0009); ergänzend Ereignisdefinition (0001) und
MES-Nachrichtenformat (0010). Es fehlt keine ADR.

---

## Block 3 – Fragen (18 min)

### Ehrlichkeitsgrenzen (wörtlich, ich sage sie aktiv, bevor sie gefragt werden)
- **Kein ML-Training, kein MLOps im Sinne von Retraining.** Die Wirkungsschätzung ist regelbasiert
  (AI4I-Regeln) plus Case-Based Reasoning. Der Eval-Teil ist MLOps-light: kein Drift-Monitoring, kein
  Retraining.
- **RAG ist bisher prototypisch.** Chunking und Re-Ranking sind nicht produktiv getuned.
- **Kein Beratungsumfeld.** Das ist ein Portfolio-PoC, keine Kundenarbeit; es sind keine fremden Daten,
  Firmen- oder Personennamen enthalten.
- **Der Simulator kennt seine eigenen Ursachen – die Konfidenz ist eine Obergrenze, kein Feldwert.**
  Trefferquote und Dauerfehler aus `evals/report.md` sind eine Obergrenze, nicht ein Ergebnis aus dem echten Werk.

### Drei wahrscheinliche Nachfragen

**1. „Kann der Agent nicht doch etwas ausführen?"**
Nein. Schritt 7 ist immer `interrupt()`; der Graph hält an. Jede Maßnahme läuft vorher durch
`action_policy.py`, Sicherheitsfunktionen (Not-Halt, Schutzeinrichtungen, Verriegelungen) sind FORBIDDEN.
IEC 62443: der Agent sitzt außerhalb der Steuerungszone und liest nur. Empfehlen ≠ Ausführen.

**2. „Woher weiß ich, dass die Empfehlung nicht halluziniert ist?"**
Jede Aussage nennt ihre Evidenz (Alarmcode, Vorfall-ID, Regel). Knoten 6 verwirft jede Maßnahme, die keine
reale Vorfall-ID aus `downtime_events_gold` belegt. Das LLM formuliert kein SQL; alle Zugriffe laufen über
den Guard. Und ich messe die Ursachen-Trefferquote gegen die verborgene Gold-Zeile – die Zahl steht im
Eval-Bericht.

**3. „Ist das nicht nur eine Demo-Kulisse – funktioniert das mit echten Daten?"**
Die Replay-Methode (ADR-0002) sorgt dafür, dass Historie und aktueller Fall aus derselben Verteilung
kommen, wie im echten Werk. Das MES-Nachrichtenformat ist OPC UA A&C / ISA-95 (ADR-0010), also
feldnah. Der Umbau zum echten MES ist eine Anbindung über OPC UA/ISA-95 statt des Simulators, keine
Neuentwicklung des Graphen. Die Grenze bleibt ehrlich benannt: der Simulator kennt seine Ursachen,
die Konfidenz ist Obergrenze.

---

## Fünf Kernsätze (frei sprechen, ohne Notiz)
1. Der Agent empfiehlt, er führt nicht aus – Schritt 7 ist immer eine menschliche Freigabe.
2. Jede Aussage nennt ihre Evidenz; Maßnahmen ohne belegte Vorfall-ID werden verworfen.
3. Historie und aktueller Fall kommen aus derselben Verteilung – der Agent sieht die Lösung nicht, ich schon,
   also kann ich messen statt behaupten.
4. Kein freies SQL, kein ML-Training – regelbasierte Schätzung plus Case-Based Reasoning, alles durch den Guard.
5. Der Simulator kennt seine Ursachen: die Konfidenz ist eine Obergrenze, kein Feldwert.
