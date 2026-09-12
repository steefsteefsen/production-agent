#!/usr/bin/env python3
"""commit-msg-Hook (Guardian K3): erzwingt die Commit-Konvention aus CLAUDE.md.

<typ>(<scope>): <Zusammenfassung>            erste Zeile ≤ 72 Zeichen (inkl. Typ und Scope)
<leer>                                       typ ∈ feat fix test docs adr sec chore · scope ∈ P A WP0–WP7 Modulname
<Body: gebaut / getestet / offen>
<leer>
Gate: grün|rot | Review: pass|fail|escalate|human | Guardian: ok
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

MAX_TITLE = 72  # erste Zeile insgesamt höchstens 72 Zeichen (Git-Standard), überall einheitlich
TITLE = re.compile(r"^(feat|fix|test|docs|adr|sec|chore)\((P|A|WP[0-9][ab]?|[a-z_]+)\): .+$")
FOOTER = re.compile(
    r"^Gate: (grün|rot) \| Review: (pass|fail|escalate|human) \| Guardian: ok$", re.M
)
EXAMPLE = "feat(WP2a): sechs fachliche MES-Werkzeuge\n\nGebaut: … Getestet: … Offen: …\n\nGate: grün | Review: pass | Guardian: ok"


def check(msg: str) -> list[str]:
    lines = [ln for ln in msg.splitlines() if not ln.startswith("#")]
    if not lines:
        return ["leere Commit-Message"]
    first = lines[0]
    if first.startswith(("Merge ", "Revert ")):
        return []
    errs = []
    if not TITLE.match(first):
        errs.append(f"Titel entspricht nicht <typ>(<scope>): <Text> – '{first[:MAX_TITLE]}'")
    if len(first) > MAX_TITLE:
        errs.append(f"Titel länger als {MAX_TITLE} Zeichen ({len(first)}) – '{first[:MAX_TITLE]}'")
    if not FOOTER.search(msg):
        errs.append("Footer fehlt: 'Gate: … | Review: … | Guardian: ok'")
    return errs


if __name__ == "__main__":
    import subprocess
    from datetime import datetime

    sys.path.insert(0, str(Path(__file__).parent))
    from guardian import check_changelog  # noqa: PLC0415

    msg = Path(sys.argv[1]).read_text(encoding="utf-8")
    errs = check(msg)

    # D5: Titel des obersten AENDERUNGEN.md-Eintrags muss gleich der ersten Commit-Zeile sein
    first_lines = [ln for ln in msg.splitlines() if not ln.startswith("#")]
    commit_title = first_lines[0].strip() if first_lines else ""
    if commit_title and not commit_title.startswith(("Merge ", "Revert ")):
        staged = subprocess.run(  # noqa: S603, S607
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        cl_proc = subprocess.run(  # noqa: S603, S607
            ["git", "show", ":docs/AENDERUNGEN.md"],
            capture_output=True,
            text=True,
        )
        cl_text = cl_proc.stdout if cl_proc.returncode == 0 else ""
        errs += check_changelog(staged, cl_text, commit_title, datetime.now().strftime("%Y-%m-%d"))

    if errs:
        print("COMMIT-MSG abgelehnt:\n - " + "\n - ".join(errs) + f"\n\nBeispiel:\n{EXAMPLE}")
        sys.exit(1)
    sys.exit(0)
