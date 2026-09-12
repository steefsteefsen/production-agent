#!/usr/bin/env python3
"""Replay-Eval (Skelett): schätzt die Kosten und verlangt --live für den kostenpflichtigen Lauf.

Nur der Live-Lauf kostet Geld – Opus über die API, Key aus .env. Das ist die einzige Stelle mit
API-Kosten (Builder/Reviewer/Decider laufen übers Abo). Ohne --live nur die Schätzung. Der
vollständige Bericht (evals/report.md) und die Fallauswahl entstehen in WP6.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PER_CASE_USD = 0.15  # grobe Schätzung Opus je Replay-Fall


def estimate() -> tuple[int, float]:
    dec = yaml.safe_load((ROOT / "decisions.yaml").read_text(encoding="utf-8"))
    n = dec.get("simulation", {}).get("replay_testfaelle", 10)
    return n, round(n * PER_CASE_USD, 2)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--live", action="store_true", help="kostenpflichtigen Live-Lauf über die API starten"
    )
    args = ap.parse_args(argv)
    n, cost = estimate()
    print(f"Replay-Eval: {n} Fälle × Opus ≈ {cost} USD (Schätzung).")
    if not args.live:
        print("Nur Schätzung. Für den Live-Lauf --live setzen (nutzt ANTHROPIC_API_KEY aus .env).")
        return 0
    if not (ROOT / ".env").exists():
        print("Kein .env mit ANTHROPIC_API_KEY – Live-Lauf nicht möglich.")
        return 1
    print("Live-Lauf: wird in WP6 implementiert (Skelett).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
