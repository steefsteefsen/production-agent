// Statische Demo-Annotationen je Graph-Knoten – EINE Quelle der Wahrheit.
// Fachlich abgeleitet aus graph/workflow.py (Knoten/Reihenfolge, interrupt am Freigabeknoten),
// decisions.yaml (einfachster Graph, keine Verzweigung), docs/testplan_e2e.md und dem
// Scope-Abschnitt der Präsentation. „Funktion" = was der Knoten tut und über welchen Weg;
// „Ausblick" = die Ausbaustufe nach Kauf (konsistent mit der Scope-Tabelle, nichts Neues).

export interface NodeAnnotation {
  funktion: string;
  ausblick: string;
}

export const NODE_ANNOTATIONS: Record<string, NodeAnnotation> = {
  capture_status: {
    funktion:
      "Liest Linienstatus und Produktionsplan über die MES-Werkzeuge get_line_status / get_production_plan – kein freies SQL, jeder Zugriff über den Guard (SELECT-only, read-only).",
    ausblick: "Am echten MES: Live-Anbindung über OPC UA / ISA-95 statt Simulator.",
  },
  analyze_alarms: {
    funktion:
      "Aggregiert das 30-Minuten-Alarmfenster und erkennt Alarmflut (ISA-18.2, ≥10 in 10 min). Werkzeugergebnisse gelten als Daten (tool_data, untrusted), nie als Anweisung.",
    ausblick: "Anomalie-Erkennung am echten MES statt fester Flut-Schwelle.",
  },
  retrieve_knowledge: {
    funktion:
      "Holt Wartungsdokumente (RAG) und ähnliche frühere Störungen (Case-Based Reasoning). Sie sind die Grundlage der späteren Beleg-Pflicht je Maßnahme.",
    ausblick: "RAG mit Re-Ranking und Chunking-Tuning (ca. 2–3 Tage).",
  },
  narrow_cause: {
    funktion:
      "Das Sprachmodell grenzt die Ursache ein und nennt eine Konfidenz; die Belege stammen aus den ähnlichen Vorfällen, nicht aus Erfindung. Die Konfidenz wird nie nachträglich erhöht.",
    ausblick: "Stärkeres Case-Based Reasoning / Verzweigung (WP4-Pfad).",
  },
  estimate_impact: {
    funktion:
      "Regelbasierte Wirkungsschätzung über das MES-Werkzeug (Stillstandskosten €/min, gefährdete Aufträge) – bewusst kein ML-Training.",
    ausblick: "Feinere Kostenmodelle je Produkt/Auftrag nach Datenlage.",
  },
  derive_actions: {
    funktion:
      "Leitet Maßnahmen ab. Nachbedingung: jede Maßnahme muss eine Vorfall-ID aus der Historie belegen. Policy: Empfehlung erst ab Konfidenz 0,60, Vier-Augen-Prinzip ab 5000 €.",
    ausblick: "Rollen-/Berechtigungsmodell, Anbindung an das Arbeitsauftrags-System.",
  },
  check_evidence: {
    funktion:
      "Ein zweites, unabhängiges Modell (LLM-as-Judge) prüft jede Maßnahme gegen ihren zitierten Beleg – mit BEWUSST getrenntem Kontext (nur Maßnahmentext + Beleg im Original, nicht die Begründung des vorschlagenden Modells). Kein Auto-Verwerfen: das Ergebnis wird nur angezeigt.",
    ausblick: "Judge-Modell je Maßnahmentyp, Schwellen und Eskalationsregeln nach Datenlage.",
  },
  approval_gate: {
    funktion:
      "Der Graph hält an (interrupt) – der Mensch entscheidet. Der Agent EMPFIEHLT, er führt NICHT aus. Freigabe oder Ablehnung wird rollenbasiert im Audit protokolliert.",
    ausblick: "Rollenmodell / AD-Anbindung, formaler Vier-Augen-Workflow.",
  },
};
