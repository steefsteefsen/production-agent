#!/usr/bin/env python3
"""commit-msg-Hook (Guardian K3): erzwingt die Commit-Konvention aus CLAUDE.md.

<typ>(<scope>): <Zusammenfassung ≤ 72>        typ ∈ feat fix test docs adr sec chore · scope ∈ P A WP0–WP7 Modulname
<leer>
<Body: gebaut / getestet / offen>
<leer>
Gate: grün|rot | Review: pass|fail|escalate|human | Guardian: ok
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TITLE = re.compile(r"^(feat|fix|test|docs|adr|sec|chore)\((P|A|WP[0-9][ab]?|[a-z_]+)\): .{1,72}$")
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
        errs.append(f"Titel entspricht nicht <typ>(<scope>): <≤72 Zeichen> – '{first[:80]}'")
    if not FOOTER.search(msg):
        errs.append("Footer fehlt: 'Gate: … | Review: … | Guardian: ok'")
    return errs


if __name__ == "__main__":
    errs = check(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if errs:
        print("COMMIT-MSG abgelehnt:\n - " + "\n - ".join(errs) + f"\n\nBeispiel:\n{EXAMPLE}")
        sys.exit(1)
    sys.exit(0)
