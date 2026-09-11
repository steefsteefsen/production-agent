# Änderungen (Was / Warum / Alternativen)

Chronologisch, neueste zuerst. Zahlen und Regelbereiche stehen bewusst nicht hier, sondern in den auto-Markern
von README/Doku (sonst veralten sie).

## Doku-Fakten nur aus Markern (Guardian D7 bis D9, K5)
**Was:** README, `docs/guardian.md` und `docs/test_strategy.md` nutzen `<!-- auto:key -->`-Marker; `autopilot/status.py --stage`
füllt sie bei jedem Commit (Hook `status-refresh`, läuft zuerst) aus Fakten (Testanzahl, Coverage, Guardian-Regeln,
Werkzeugzahl, Paketstand, Hooks, letzter Commit). Neue Regeln: D7 (Marker aktuell), D8 (keine getippten Fakten außerhalb
Markern), D9 (Stand-Abschnitt), K5 (pre-commit-`entry` beginnt mit `.venv/bin/python`).
**Warum:** Das README nannte eine veraltete Testanzahl und alte Regelbereiche; handgeschriebene Zahlen veralten still.
**Alternativen:** Handkorrektur – verworfen, weil sie sich wiederholt. LLM-Prüfung im Hook – verworfen wegen Kosten und
Nichtdeterminismus (bleibt manuell über `--llm`).

## Geheimnisse von Konfiguration getrennt (Guardian S7 streng)
**Was:** `settings.env` (committet) hält Konfiguration, `.env` (gitignored) nur noch Geheimnisse (Schlüssel auf
KEY/SECRET/TOKEN/PASSWORD). `config.py` liest `("settings.env", ".env")`, `.env` überschreibt. Guardian S7 verbietet jeden
`.env`-Wert (Länge ≥ acht) in anderen Dateien ohne Ausnahme; S7b prüft die Schlüsselnamen, S7c die `-EXAMPLE`-Endung.
**Warum:** S7 meldete bislang Konfigurationswerte (Modellname, Pfade) als vermeintliches Leck.
**Alternativen:** Schlüsselmuster-Heuristik – verworfen, weil sie die Regel aufweicht. Suffix nur in `.env.example` – verworfen,
weil die echte `.env` die Kollision verursacht.

## Projektstatus als JSON + HTML im Commit-Hook, Coverage-Grenzen (K4)
**Was:** `autopilot/status.py` erzeugt `docs/status/status.json` und `index.html` deterministisch aus tasks.yaml, Journal,
git, Coverage und Guardian; der Hook `status-refresh` schreibt und staged sie. Guardian D6 hält den Stand frisch, K4 setzt
Coverage-Grenzen (pytest-cov, `--cov-fail-under`).
**Warum:** Fortschritt und Zeitstempel sollen aus dem Repo kommen, nicht aus manuellem Einfügen; Coverage soll ein Gate sein.
**Alternativen:** Status nur im Cockpit per Einfügen – verworfen, weil nicht konsistent. Coverage nur in CI – verworfen, weil zu spät.
