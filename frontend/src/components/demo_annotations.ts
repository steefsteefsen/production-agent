// Statische Demo-Annotationen je Graph-Knoten – EINE Quelle der Wahrheit.
// Fachlich abgeleitet aus graph/workflow.py (Knoten/Reihenfolge, interrupt am Freigabeknoten),
// decisions.yaml (Konfidenzschwelle, Vier-Augen, einfachster Graph) und den ADRs.
// "Funktion" = was der Knoten tut und über welchen Weg (Block TRANSFORMATION);
// "Bewertung" = warum dieser Schritt und dieses Werkzeug (geerdet in decisions.yaml/ADR);
// "Ausblick" = Ausbaustufe nach Kauf / weitere Schritte (Block BEWERTUNG, "weitere Schritte").

export interface NodeAnnotation {
  funktion: string;
  bewertung: string;
  ausblick: string;
}

export const NODE_ANNOTATIONS: Record<string, NodeAnnotation> = {
  capture_status: {
    funktion:
      "Liest Linienstatus und Produktionsplan über die MES-Werkzeuge get_line_status / get_production_plan – kein freies SQL, jeder Zugriff über den Guard (SELECT-only, read-only).",
    bewertung:
      "Zuerst der Faktenstand: ohne Linienstatus/Plan keine belastbare Analyse. Werkzeug statt freiem SQL, weil jeder DB-Zugriff über den Guard läuft (Allowlist, Row-Limit, read-only – ADR-0002/0005).",
    ausblick: "Am echten MES: Live-Anbindung über OPC UA / ISA-95 statt Simulator.",
  },
  analyze_alarms: {
    funktion:
      "Aggregiert das 30-Minuten-Alarmfenster und erkennt Alarmflut (ISA-18.2, ≥10 in 10 min). Werkzeugergebnisse gelten als Daten (tool_data, untrusted), nie als Anweisung.",
    bewertung:
      "Alarme sind das primäre Störungssignal; die Flut-Erkennung (ISA-18.2) verhindert, dass Einzelalarme die Ursache verdecken. Bewusst regelbasiert statt LLM – deterministisch und prüfbar.",
    ausblick: "Anomalie-Erkennung am echten MES statt fester Flut-Schwelle.",
  },
  retrieve_knowledge: {
    funktion:
      "Holt Wartungsdokumente (RAG) und ähnliche frühere Störungen (Case-Based Reasoning). Sie sind die Grundlage der späteren Beleg-Pflicht je Maßnahme.",
    bewertung:
      "Erst Belege sammeln, dann urteilen: RAG-Dokumente + ähnliche Vorfälle tragen die Beleg-Pflicht (ADR-0004). Werkzeug statt LLM-Gedächtnis, damit nichts erfunden wird; immer_wissen_abrufen=true (decisions.yaml).",
    ausblick:
      "RAG mit echter Vektor-Suche (Embeddings ingesten), Re-Ranking und Chunking-Tuning (ca. 2–3 Tage).",
  },
  narrow_cause: {
    funktion:
      "Das Sprachmodell grenzt die Ursache ein und nennt eine Konfidenz; die Belege stammen aus den ähnlichen Vorfällen, nicht aus Erfindung. Die Konfidenz wird nie nachträglich erhöht.",
    bewertung:
      "Hier ist Sprachverständnis nötig (unstrukturierte Doku + Fallmuster) → LLM-Knoten. Konfidenz = 0,5·Regeltreffer + 0,3·Fallähnlichkeit + 0,2·Ursachenanteil (decisions.yaml); der Kern-Prompt verbietet Erhöhung.",
    ausblick: "Stärkeres Case-Based Reasoning / Verzweigung (WP4-Pfad).",
  },
  estimate_impact: {
    funktion:
      "Regelbasierte Wirkungsschätzung über das MES-Werkzeug (Stillstandskosten €/min, gefährdete Aufträge) – bewusst kein ML-Training.",
    bewertung:
      "Wirtschaftliche Priorisierung braucht eine Zahl (Hochleistungslinie ~200 €/min). Regelbasiertes MES-Werkzeug statt ML – nachvollziehbar, kein Trainingsaufwand vor dem Kauf.",
    ausblick: "Feinere Kostenmodelle je Produkt/Auftrag nach Datenlage.",
  },
  derive_actions: {
    funktion:
      "Leitet Maßnahmen ab. Nachbedingung: jede Maßnahme muss eine Vorfall-ID aus der Historie belegen. Policy: Empfehlung erst ab Konfidenz 0,60, Vier-Augen-Prinzip ab 5000 €.",
    bewertung:
      "Aus Ursache + Wirkung konkrete Handlungen → LLM (Formulierung/Abwägung). Schwelle 0,60 bewusst früh (Techniker prüft ohnehin vor Ort), Vier-Augen ab 5000 € – Geschäftsentscheidung des Werks (decisions.yaml).",
    ausblick: "Rollen-/Berechtigungsmodell, Anbindung an das Arbeitsauftrags-System.",
  },
  check_evidence: {
    funktion:
      "Ein zweites, unabhängiges Modell (LLM-as-Judge) prüft jede Maßnahme gegen ihren zitierten Beleg – mit BEWUSST getrenntem Kontext (nur Maßnahmentext + Beleg im Original, nicht die Begründung des vorschlagenden Modells). Kein Auto-Verwerfen: das Ergebnis wird nur angezeigt.",
    bewertung:
      "Die Selbst-Belegung aus Knoten 6 stammt vom selben Modell – deshalb ein zweites (Haiku) mit anderer Kontextscheibe (ADR-0011). Kein automatisches Verwerfen, damit der Mensch entscheidet (empfehlen ≠ ausführen).",
    ausblick: "Judge-Modell je Maßnahmentyp, Schwellen und Eskalationsregeln nach Datenlage.",
  },
  approval_gate: {
    funktion:
      "Der Graph hält an (interrupt) – der Mensch entscheidet. Der Agent EMPFIEHLT, er führt NICHT aus. Freigabe oder Ablehnung wird rollenbasiert im Audit protokolliert.",
    bewertung:
      "Empfehlen ≠ ausführen ist das tragende Prinzip: echter interrupt()/Resume über den Checkpointer, Timeout 30 min (Vorschlag verfällt), rollenbasiertes Audit jeder Entscheidung (decisions.yaml, ADR-0002).",
    ausblick: "Rollenmodell / AD-Anbindung, formaler Vier-Augen-Workflow.",
  },
};
