# Ops-Cockpit

Lokale Steuerungsoberfläche für den Orchestrator-Betrieb. Unabhängig vom Produktionsleiter-Frontend.

## Starten

```bash
make ops        # http://localhost:8010 mit Auto-Reload
# oder direkt:
uvicorn autopilot.ops.app:app --host 127.0.0.1 --port 8010
```

Nur lokaler Zugriff (127.0.0.1 / ::1). Die App startet keinen Browser.

## Tabs

### Ablauf

- Lanes als Zeilen, Arbeitspakete als farbige Kacheln:
  - grau = ausstehend · salbei = bereit · blaugrün = läuft · grün = Gate ✓ · olivgrün = Review ✓
  - blau = gemergt · weinrot = eskaliert/erschöpft · orange = blockiert · lila = Quota
- Kacheln klickbar → Gate-Ausgabe, Reviewer-Urteil, Sync-Paket-Link
- Live-Tail des laufenden WP-Logs (`autopilot/logs/orch-<WP>.log`, letzte 40 Zeilen)
- Letzte 20 Journal-Einträge aus `autopilot/journal/*.json`
- Polling: alle 5 Sekunden

### Stand

Kennzahlen aus `docs/status/status.json` (Pakete, Fortschritt, Coverage, Kosten).
Inhalt von `ESCALATION.md`.

**Aktionen:**

| Aktion | Beschreibung |
|---|---|
| Dry-Run anzeigen | `orchestrate.py --dry-run`, Ausgabe im Browser |
| Starten | Orchestrator als Hintergrundprozess (Flags: `--auto-decide`, `--push`, Budget) |
| Stoppen | SIGTERM an den laufenden Orchestrator; laufende Builder dürfen enden |
| Retry `<WP>` | `orchestrate.py --retry <WP>` |
| Skip `<WP>` | `orchestrate.py --skip <WP> --yes` (mit Browser-Bestätigung) |
| Sync-Paket | `sync.py <WP>` |

### Konfiguration

- **Konfigurierbare Felder** (editierbar über Dropdown/Slider):
  - `alarm_prioritaet.verfahren` – Prioritätsverfahren (ISA-18-Matrix oder Hersteller-Severity)
  - `audit.personenbezug` – Pseudonymisierungsstufe im Audit
  - `konfidenz.schwelle_empfehlung` – ab welcher Konfidenz der Agent eine Empfehlung ausspricht
- Speichern schreibt **nicht** in `decisions.yaml` (Guardian S5), sondern in `config/runtime.yaml`
  mit Audit-Zeile (Zeit, Feld, alt → neu, Rolle „Stefan") in `config/ops_audit.jsonl`.
- **Aktive Constraints** – Kartenliste der aktuell wirksamen Regeln (Ereignis, Schwelle, Rollen, Vier-Augen, Timeout, Priorität).
- `decisions.yaml` vollständig als read-only Textblock (Änderung nur über `decisions.yaml` + `GUARDIAN_ALLOW_DECISIONS`).

### Präsentation

Bettet `docs/presentation/index.html` als iframe ein.

## Sicherheit

- Nur 127.0.0.1 / ::1; fremde Hosts erhalten 403.
- Keine Shell-Freitexteingaben; alle Aktionen rufen feste Subprozess-Argumente auf.
- Jede Aktion (Start, Stop, Retry, Skip, Sync, Config-Änderung) wird in `config/ops_audit.jsonl` protokolliert.

## Tests

```bash
pytest tests/test_ops.py -q --no-cov
```

Abgedeckt: Verifikation (Tabs, Lanes, Config-Felder, runtime.yaml + Audit) und
Falsifikation (nicht-konfigurierbares Feld → 403, decisions.yaml unverändert, unbekanntes WP → 404).
