# ADR-0011: Unabhängige Beleg-Prüfung der Maßnahmen (LLM-as-Judge)

Datum: 2026-09-14 · Status: akzeptiert

## Kontext
Knoten 6 leitet Maßnahmen ab und muss je Maßnahme eine Vorfall-ID aus der Historie als Beleg
nennen (Nachbedingung Knoten 6). Diese Selbst-Belegung stammt jedoch aus demselben Modell und
Kontext, der die Maßnahme vorschlägt – das Modell kann seine eigene Begründung bestätigen, ohne
dass der Beleg die Maßnahme wirklich stützt. Vor dem Freigabeknoten (interrupt) fehlte eine
unabhängige Kontrolle. `LLM_MODEL_JUDGE` (ein kleineres, schnelleres Modell) war in settings.env
bereits definiert, wurde im Live-Graphen aber nirgends genutzt.

## Optionen (mind. 3) mit Bewertung
1. **Nichts ändern, nur die Selbst-Belegung aus Knoten 6.** Einfach, aber keine unabhängige
   Kontrolle – das vorschlagende Modell prüft sich selbst.
2. **Judge-Knoten, der bei fehlendem Beleg die Maßnahme automatisch verwirft.** Stark, aber
   verschiebt die Entscheidung wieder in die Automatik – widerspricht dem Grundsatz „der Agent
   empfiehlt, der Mensch entscheidet" und kann korrekte Maßnahmen fälschlich unterdrücken.
3. **Judge-Knoten mit bewusst getrenntem Kontext, Ergebnis nur anzeigen (gewählt).** Ein zweites,
   unabhängiges Modell prüft jede Maßnahme NUR gegen (a) den Maßnahmentext und (b) den zitierten
   Beleg im Original – nicht gegen die Hypothese aus Knoten 4 oder die Begründung/Konversation aus
   Knoten 6. So kann es die Begründung des Vorschlags nicht übernehmen. Kein Auto-Verwerfen: das
   Ergebnis (verified + judge_note) wird durchgereicht und am Freigabeknoten sichtbar gemacht.

## Entscheidung
Option 3. Neuer linearer Knoten „Beleg-Prüfung" (`check_evidence`) zwischen Knoten 6 und dem
Freigabe-Gate. Er ruft je Maßnahme das Judge-Modell (`LLM_MODEL_JUDGE`) mit strikt getrenntem
Kontext auf (`graph/judge.py`), sammelt `judge_results` (verified, judge_note je Maßnahme) und
reicht sie an das Gate weiter. Der Graph bleibt linear – keine neue Verzweigung, kein Eingriff in
die Knoten 1–6. Die Kontext-Trennung ist das tragende Design-Prinzip: unabhängige Prüfung statt
Selbstbestätigung. Kein automatisches Verwerfen unbestätigter Maßnahmen; die Entscheidung bleibt
beim Menschen am interrupt.

## Konsequenzen / Kurzfassung für die Präsentation
- Vor jeder Freigabe prüft ein zweites, unabhängiges Modell jede Maßnahme gegen ihren Beleg – mit
  anderem Kontext als das vorschlagende Modell. Nicht bestätigte Maßnahmen werden nicht versteckt
  und nicht automatisch verworfen, sondern am Freigabe-Gate rot markiert; der Mensch entscheidet.
- Deterministisch testbar über das Mock-LLM (bestätigt bei vorhandenem Beleg, lehnt bei
  fehlendem/manipuliertem Beleg ab). Kein ML-Training, keine neue Verzweigungslogik.
- Grenze: Der Judge bewertet nur die Beleg-Stützung, nicht die technische Richtigkeit der Maßnahme;
  er ersetzt weder die Freigabe noch das Audit.

## Quellen (mit Datum)
- ADR-0002 (Entscheidungsbasis/Replay, kein Gold-Leck) · 2026-09
- ADR-0006 (Konfidenzschwelle) · 2026-09
- settings.env: `LLM_MODEL_JUDGE` · 2026-09
