#!/usr/bin/env python3
"""Gate-Baustein: die Abnahmetests eines WP müssen laufen und grün sein – 0 Skips.

Solange ein WP nicht gebaut ist, überspringen seine Abnahmetests (importorskip/skipif). Dieses Gate
verlangt, dass am Ende KEIN Abnahmetest mehr übersprungen wird – sonst gilt das WP nicht als erfüllt.

  python autopilot/gate_no_skip.py WP3   → Exit 0 (0 Skips, alle grün) oder 1
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def acceptance_file(wp: str) -> Path:
    return ROOT / "tests" / "acceptance" / f"test_{wp.lower().replace('-', '')}.py"


def main(wp: str) -> int:
    f = acceptance_file(wp)
    if not f.exists():
        print(f"gate_no_skip: {f.relative_to(ROOT)} fehlt")
        return 1
    r = subprocess.run(
        [sys.executable, "-m", "pytest", str(f), "-q", "-rs", "-o", "addopts="],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    out = r.stdout + r.stderr
    m = re.search(r"(\d+) skipped", out)
    skipped = int(m.group(1)) if m else 0
    if r.returncode != 0 or skipped > 0:
        print(
            f"gate_no_skip {wp}: {skipped} Skips, rc={r.returncode} – Abnahmetests müssen laufen und grün sein"
        )
        return 1
    print(f"gate_no_skip {wp}: 0 Skips, alle grün")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]) if len(sys.argv) > 1 else 1)
