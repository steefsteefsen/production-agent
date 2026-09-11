# ADR-0002: Entscheidungsbasis durch Replay, nicht durch Erfindung

Datum: 2026-09-10 · Status: akzeptiert

## Kontext
Die Aufgabenstellung verlangt ein *simuliertes* MES, Alarmanalyse und historisches Wissen. Die zentrale Frage:
Woher kommt die Entscheidungsbasis für den aktuellen Fall, wenn alles simuliert ist?

## Optionen
1. **Zwei getrennte Simulationen** – eine Historie, ein handgeschriebener „aktueller Fall". Schnell, aber der aktuelle Fall
   stammt aus einer anderen Verteilung als die Historie; die Eval wäre wertlos.
2. **Echte Datensätze (ALPI, AI4I) als Historie, aktueller Fall daraus ausgeschnitten.** Realistisch, aber ALPI braucht
   IEEE-Login, hat keine Aufträge/Kosten/Maßnahmen und kostet Mapping-Zeit.
3. **Ein Generator, ein Medallion, ein Cursor (gewählt).** Der Simulator erzeugt die gesamte Historie inklusive
   Auflösung (Ursache, Maßnahme, Dauer) und schreibt sie durch Bronze → Silber → Gold. „Jetzt" ist eine Replay-Uhr
   kurz nach Beginn eines Gold-Ereignisses. Alles davor ist Historie mit bekannter Lösung; das Ereignis selbst ist
   für den Agenten offen. Seine Gold-Zeile ist die verborgene Wahrheit.

## Entscheidung
Option 3. AI4I-Wertebereiche und -Ausfallregeln fließen als Sensor-Snapshot je Ereignis ein (Regeln bleiben
zitierbar); ALPI wird als Struktur-Referenz genannt und kann als Bronze-Quelle ergänzt werden, ist aber kein Blocker.

## Konsequenzen
- Jedes MES-Werkzeug filtert auf `ts <= now` bzw. `end_ts <= now` – kein Leck der laufenden Störung.
- Die Eval fällt gratis ab: n jüngste Gold-Ereignisse als Replay-Fälle, Vorhersage (Ursache, Dauer, Maßnahme)
  gegen Gold-Zeile → Trefferquote und Dauerfehler. Das ist die MLOps-light-Schicht, ehrlich benannt.
- Kurzfassung für die Präsentation: „Historie und aktueller Fall kommen aus derselben Verteilung, wie im echten Werk.
  Der Agent sieht die Lösung nicht – ich schon. Deshalb kann ich messen, statt zu behaupten."
- Grenze: Der Simulator kennt seine eigenen Ursachen; Konfidenz-Ergebnisse sind Obergrenze, nicht Feldwert.
