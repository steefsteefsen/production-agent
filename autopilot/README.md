# Autopilot

```bash
claude auth status                      # CLI angemeldet?
python autopilot/run.py --dry-run       # alle Prompts mit gefüllten Platzhaltern ansehen
python autopilot/run.py                 # alles der Reihe nach, jedes WP bis Gate grün
python autopilot/run.py --only WP3 WP4  # einzelne WPs
```

- `decisions.yaml` ist die einzige Datei, die du vorher anfasst.
- Jedes WP läuft in `claude -p` mit `--permission-mode dontAsk`, `--max-turns`, `--max-budget-usd`; Rechte aus `.claude/settings.json`.
- Gate rot → Ausgabe wird dem Subagent zurückgespielt (Standard 2 Wiederholungen). Danach Stopp, du schaust ins Log.
- `autopilot/status.json` passt zum Import-Feld im Projekt-Cockpit (Tab 1).
- Parallel: WP1‖WP2a, WP2b‖WP3, WP4‖WP5 sind unabhängig. Für parallele Läufe je WP einen `git worktree` anlegen und `run.py --only` darin starten; das Zusammenführen bleibt bei dir.

- `--review` hält nach jedem grünen Gate an (Checkliste, j/n). `--narrate` lässt Haiku den Diff in drei Sätzen erzählen (Cent-Beträge). `--no-commit` unterdrückt den Commit je WP.
- `autopilot/journal.md` ist das lesbare Vorgehen, `journal.json` der Import für Tab 7 im Cockpit.
- `--review auto|human|both|off` (Standard auto): kontextfreier Reviewer (`--review-model opus`) urteilt per JSON-Schema; nur `fail`/`escalate` erreichen dich.
- `python autopilot/sync.py WP3` baut das Sync-Paket für den Chat; `--status` schreibt STATUS.md fürs Projektwissen. Siehe docs/chat_interface.md.
