# ADR-0006: Konfidenzschwelle und Konfidenzformel für Knoten 4

Datum: 2026-09-13 · Status: akzeptiert

## Kontext
Knoten 4 des Agenten grenzt die Ursache eines Stillstands ein und gibt eine Konfidenz aus.
Diese Konfidenz steuert, ob eine Maßnahme als Empfehlung oder nur als Hypothese angezeigt wird
(decisions.yaml `konfidenz.schwelle_empfehlung`).
Die Kennzahl muss erklärbar sein (EU-AI-Act Art. 13 – Transparenz), reproduzierbar
und unabhängig von der Stimmung des LLM.

## Optionen

| Option | Formel | Vorteil | Nachteil |
|---|---|---|---|
| **A (gewählt)** | 0.5·regeltreffer + 0.3·beste_fallaehnlichkeit + 0.2·ursachenanteil, LLM kann nur senken | erklärbar, auditierbar, robust gegen LLM-Überschätzung | Bausteine müssen aus DB geladen werden (ai4i_snapshots) |
| B | LLM-Konfidenz direkt | einfach | nicht prüfbar, Halluzinations-Risiko |
| C | Precision/Recall gegen Gold-Labels in Offline-Eval | statistisch korrekt | braucht viele echte Labels, nur für Offline-Evaluation, nicht für Live-Score |

### Bewertung Precision / Recall vs. Accuracy

Bei einer Ausfallrate von ca. 3,4 % im AI4I-Datensatz wäre Accuracy irreführend
(99 % „nie ausfallen" = 96,6 % Genauigkeit). Precision und Recall sind die korrekten
Metriken für seltene Ereignisse (ISO 13849 betrachtet Auftrittswahrscheinlichkeiten
vergleichbar). Für die Offline-Evaluation gelten daher:
- Precision = TP / (TP + FP): wie viele Empfehlungen waren korrekt?
- Recall = TP / (TP + FN): wie viele Ausfälle wurden erkannt?

### Kosten Falsch-Positiv vs. Falsch-Negativ

| Fehlerart | Konsequenz | Kosten (geschätzt) |
|---|---|---|
| Falsch-Positiv (unnötige Empfehlung) | Techniker prüft vor Ort → 5–15 min | 1 000–3 000 € |
| Falsch-Negativ (Ausfall verpasst) | ungeplanter Stillstand verlängert sich | 10 000–50 000 € |

Ein Falsch-Negativ kostet eine Größenordnung mehr. Die Schwelle sollte daher eher niedrig gewählt
werden (hoher Recall), solange ein Mensch vor Ort jede Empfehlung prüft.

## Entscheidung

Option A. Schwelle 0.60 (aus decisions.yaml `konfidenz.schwelle_empfehlung`).

**Begründung Arbeitspunkt 0.60:** Auf einer Hochleistungslinie mit 200 €/min ist eine
Empfehlung mit 60 % Konfidenz billiger als zehn Minuten Warten auf 70 %: der Techniker prüft
vor Ort ohnehin, ein Fehlvorschlag kostet Minuten, ein verpasster kostet Tausende.
Der Wert ist eine Geschäftsentscheidung des Werks und im Cockpit sichtbar
(`konfidenz.schwelle_empfehlung`, configurable: true).

**Formel:**
```
konfidenz = 0.5 * regeltreffer + 0.3 * beste_fallaehnlichkeit + 0.2 * ursachenanteil_gleiche_faelle
```
- `regeltreffer`: Anteil ähnlicher Gold-Fälle mit ≥1 ausgelöster AI4I-Regel (TWF/HDF/PWF/OSF)
- `beste_fallaehnlichkeit`: höchster CBR-Score nach Jaccard(Alarmcodes) + PackML + Regelmodi
- `ursachenanteil_gleiche_faelle`: Anteil ähnlicher Fälle mit gleicher reason_code wie Hypothese

**Nachbedingung (erzwungen):** `hypothesis.confidence = min(llm_confidence, regel_konfidenz)`.
Das LLM darf die berechnete Konfidenz nur senken, nicht erhöhen.

## Konsequenzen

- `confidence_parts` im AgentState macht die Bausteine auditierbar
  (rule_score, cbr_score, cause_score, computed, llm, final).
- `rule_modes` im AgentState enthält die ausgelösten Regelcodes (TWF/HDF/PWF/OSF)
  für das Cockpit und das Audit-Log.
- Die Schwelle ist im Cockpit (Tab Config) sichtbar und änderbar; Änderungen werden auditiert.
- Für den Offline-Arbeitspunkt: Replay-Eval mit Precision/Recall über replay_testfaelle Gold-Fälle.

## Quellen (mit Datum)

- UCI AI4I 2020 Machine Learning Dataset, CC BY 4.0, id 601 (abgerufen 2026-09)
- decisions.yaml `konfidenz.*`, `freigabe.vier_augen_ab_kosten_eur`, `linie.cost_per_downtime_minute_eur`
- EU-AI-Act Art. 13 (Transparenz) – Pflicht zur Erklärbarkeit von Empfehlungssystemen
- ADR-0002 (Replay-Entscheidungsbasis), ADR-0001 (Ereignisdefinition)
