# Konsolidierter Änderungsverlauf (Interview-Vorbereitung)

Chronologische Kurzübersicht der Arbeit vom 15.–16.09.2026, neueste zuerst. Je Zeile ein Satz **Was**
und ein Satz **Warum/Fund**; Details stehen im jeweiligen Commit, in [AENDERUNGEN.md](AENDERUNGEN.md)
und den verlinkten ADRs. Zahlen bewusst nicht hier (siehe Statusseite/`decisions.yaml`).

## 2026-09-16
- **`80207bb` docs(readme): Setup-Anleitung + bekannte Altlasten** — Was: README als reproduzierbare
  Setup-/Start-Anleitung (Timing, `--reload`-Workaround, URL-Tabelle, Architektur-Überblick). Warum:
  letzte Interview-Vorbereitung, Start von Null muss ohne Rückfragen laufen.
- **`71430b0` fix(live_daten): Stationen zeigen SIM_NOW-Zustand** — Was: `/mes/line` filtert den
  PackML-Zustand auf `s.ts <= SIM_NOW` und verknüpft eine gestörte Station mit dem aktiven Ereignis;
  Störungsstrom gruppiert/farbcodiert. Fund: der Endpunkt nahm den global jüngsten Zustand (alle
  Stationen „Execute") und widersprach damit dem Störungsstrom.
- **`f218e98` fix(mock_llm): Rückkopplungstext je reason_code** — Was: die Mock-Vervollständigung
  leitet den Beispieltext aus dem tatsächlichen `reason_code` ab. Fund: bei STO-ANTRIEB erschien
  fälschlich der STO-FOLIE-Beispieltext.

## 2026-09-15
- **`3c44517` fix(ui): Zustandspersistenz, Ereignis-Auswahl, RAG-Chunk + Vektor-Fix** — Was: fünf
  Testbefunde behoben plus eine dauerhafte Regressionssuite gegen den echten Pfad. Fund u. a.: die
  Vektor-Suche war trotz Dependency tot (`client.search()` → `query_points`).
- **`834d25f` fix(api): Demo-Default In-Process** — Was: der Demo-Default läuft in-process, damit die
  Replay-Uhr `SIM_NOW` je Anfrage greift. Fund (N-1): im MCP-Subprozess-Pfad war `SIM_NOW`
  eingefroren → STO-UNBEKANNT statt STO-FOLIE.
- **`3d812a1` / `21f822e` / `f872c37` feat/fix(ui): Sechs-Tab-Cockpit** — Was: Cockpit mit Bediener,
  Live-Daten, MCP-Timeline, Wissen/RAG-Landkarte, Sicherheit, Konfiguration auf echten Daten; Graph-
  Linearität präzise dargestellt. Warum: eine geführte, ehrliche Demo-Oberfläche fürs Interview.
- **`e6661df` feat(agent_tab): Freigabe-Seite** — Was: eigenständige Freigabe-Seite mit
  Konfidenzbalken, Policy-Badges und Original-Belegtext. Warum: die menschliche Freigabe sichtbar und
  belegt machen ([ADR-0011](adr/0011-beleg-pruefung-judge.md)).
- **`6dbe1ea` fix(audit): MCP-Protokoll-Default, Konfidenzschwelle-Drift** — Was: Audit-Befunde
  behoben, die angewandte Schwelle in State/Trace + Ops-Drift-Warnung. Fund: `runtime.yaml`-Override
  driftete vom `decisions.yaml`-Default ab.

## Voller Sitzungsbericht (lokal)
Der ausführliche Freeze-/Testbericht der Sitzung liegt als lokales Arbeitsdokument in
`docs/freeze_2026-09-16.md` (nicht committet, enthält getippte Kennzahlen/Screenshots).
