#!/usr/bin/env python3
"""Abschluss-Veröffentlichung in einem Befehl: Cockpit auffrischen → Guardian → konform committen → pushen.

  python autopilot/publish.py --title "fix(infra): …" --body "Gebaut: … Getestet: … Offen: … Warum: …"

Der Titel muss der Commit-Konvention folgen (commit_check: <typ>(<scope>): <Text>, ganze Zeile ≤ 72). Der
Footer 'Gate: … | Review: … | Guardian: ok' wird angehängt. --no-push committet nur (kein Push).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import commit_check  # noqa: E402


def sh(*args: str, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=ROOT, text=True, **kw)  # noqa: S603


def build_message(title: str, body: str, gate: str = "grün", review: str = "human") -> str:
    footer = f"Gate: {gate} | Review: {review} | Guardian: ok"
    body = body.strip() or "Gebaut: – Getestet: – Offen: – Warum: –"
    return f"{title}\n\n{body}\n\n{footer}\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--title", required=True, help="Commit-Titel (<typ>(<scope>): <Text>, ≤ 72 Zeichen)"
    )
    ap.add_argument("--body", default="", help="Gebaut/Getestet/Offen/Warum")
    ap.add_argument("--gate", default="grün", choices=["grün", "rot"])
    ap.add_argument("--review", default="human", choices=["pass", "fail", "escalate", "human"])
    ap.add_argument("--no-push", action="store_true", help="nur committen, nicht pushen")
    args = ap.parse_args(argv)

    msg = build_message(args.title, args.body, args.gate, args.review)
    errs = commit_check.check(msg)  # vor jeder Arbeit prüfen, damit nichts halb passiert
    if errs:
        print("Titel/Message nicht konform:\n - " + "\n - ".join(errs))
        return 1

    sh(sys.executable, "autopilot/status.py", "--stage")  # Marker/Status frisch (D6/D7)
    sh(sys.executable, "autopilot/present.py", "--stage")  # Präsentation frisch
    sh(
        sys.executable, "-m", "ruff", "format", "."
    )  # formatieren VOR git add (Guardian K2 prüft nur)
    sh(sys.executable, "-m", "ruff", "check", "--fix", "-q", ".")
    sh("git", "add", "-A")
    if sh(sys.executable, "autopilot/guardian.py").returncode != 0:
        print("Guardian rot – Abbruch (nichts committet).")
        return 1

    c = sh("git", "commit", "-m", msg, capture_output=True)
    print((c.stdout + c.stderr).strip())
    if c.returncode != 0 and "nothing to commit" not in (c.stdout + c.stderr):
        sh("git", "add", "-A")  # zweiter Anlauf: pre-commit-Hooks haben Dateien umformatiert
        c = sh("git", "commit", "-m", msg, capture_output=True)
        print((c.stdout + c.stderr).strip())
    if c.returncode != 0 and "nothing to commit" not in (c.stdout + c.stderr):
        print("Commit fehlgeschlagen.")
        return 1

    if args.no_push:
        return 0
    for push in (["git", "push"], ["git", "push", "--tags"]):
        p = sh(*push, capture_output=True)
        print(f"$ {' '.join(push)}\n{(p.stdout + p.stderr).strip()}")
        if p.returncode != 0:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
