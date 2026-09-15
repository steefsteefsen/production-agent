// Kuratierte Präsentationsinhalte – 1:1 übernommen aus autopilot/present.py (SCOPE_DECISIONS,
// STACK_DECISIONS). Ab jetzt ist DIESE React-Quelle der Demo-Inhalt; das Ops-Cockpit bindet die
// React-App per iframe ein und pflegt keine eigene HTML-Tabelle mehr.

export interface TableSpec {
  title: string;
  columns: string[];
  rows: string[][];
  anchor: string;
}

export const SCOPE: TableSpec = {
  title: "Scope-Entscheidungen – Aufwand gering halten, bevor der Kunde kauft",
  columns: ["Abkürzung im PoC", "Warum – was der PoC validiert", "Ausbau nach Kauf"],
  rows: [
    ["Kein ML-Training", "PoC beweist den agentischen Ablauf, nicht Modellgüte", "Feintuning/Klassifikator nach Datenlage"],
    ["RAG prototypisch (aktuell BM25-only)", "reicht zur Validierung der Beleg-Pflicht je Maßnahme", "Embeddings ingesten (Vektor-Seite anschalten), Re-Ranking ~2–3 Tage"],
    ["Ein Replay-Fall statt Eval-Harness", "erst wenn der Ablauf überzeugt, lohnt Messbreite", "Eval über 20+ Fälle mit Metriken ~3 Tage"],
    ["Simulator kennt seine Ursachen", "bewusst – nur so ist reason_hit prüfbar", "am echten MES: Gold-Labels aus der Instandhaltung"],
    ["CI testet nur Existierendes", "Badge grün = ehrlich", "Browser-E2E gegen Cockpit ~2 Tage"],
    ["Einfachster Graph ohne Verzweigung", "Nachvollziehbarkeit vor Raffinesse", "Verzweigung/CBR (WP4-Pfad)"],
  ],
  anchor: "Dokumentiert in Testplan/ADRs, je mit Ausbau-Aufwand – gescoped, nicht unfertig.",
};

export const STACK: TableSpec = {
  title: "Technologie-Entscheidungen – bewusst gewählt, jede belegbar",
  columns: ["Kategorie", "Entscheidung bei uns", "Begründung"],
  rows: [
    ["LLMs", "Claude Sonnet 5 (Knoten 4/6) + Haiku (Judge)", "ein Anbieter bewusst; der PoC beweist die Architektur, nicht Vendor-Abstraktion"],
    ["Framework", "LangGraph", "State-Machine mit interrupt() + SQLite-Checkpointer; kein Multi-Agent-Overhead nötig"],
    ["Retrieval", "BM25 (rank_bm25); Vektor-Seite (Qdrant + e5-small) angelegt, aktuell inaktiv → real BM25", "an Exakt-/Synonym-/Negativfall geprüft; Vektor bräuchte Embeddings-Ingest; Negativfall ohne Score-Schwelle ist bekannte Grenze (Testplan E5)"],
    ["Data Ingestion", "keine; synthetische Daten (Simulator) + fester Dokumentenbestand", "PoC-Scope; echte Erfassung (OPC UA/ISA-95) ist der erste Ausbauschritt"],
    ["Observability", "Langfuse (WP6), optional aktivierbar", "eingebaut, real noch nicht gegen einen laufenden Server verifiziert – offener Punkt"],
    ["Deployment/Infra", "lokal (uvicorn + Vite); kein Docker/K8s für die App", "Deployment-Entscheidung erst nach Kern-Validierung sinnvoll"],
    ["Evaluation", "eigener Replay-Eval mit Gold-Wahrheit statt Ragas/DeepEval", "domänenspezifische Gold-Fälle präziser als generische Faithfulness-Metriken"],
    ["LLM-as-Judge", "aktiv im Graphen (Knoten 7, Haiku, getrennter Kontext)", "zweites unabhängiges Modell prüft Maßnahmen-Belege; kein Auto-Verwerfen"],
  ],
  anchor: "Jede Zeile spiegelt den echten Code-/Log-Stand – keine Behauptung ohne Beleg.",
};
