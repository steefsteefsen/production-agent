#!/usr/bin/env python3
"""Browser-Konsolencheck für das Cockpit / den Agent-Tab (localhost:5173) mit Playwright.

Dauerhaft, nicht Wegwerf: bestätigt nach Änderungen, dass der Agent-Tab ohne Konsolenfehler lädt
UND der Kern-Ablauf (Start → Beleg-Prüfung durch den Judge → Freigabe erforderlich) intakt ist.
Pflichtbedingung: 0 Browser-Konsolenfehler. Screenshots nach docs/demo_walkthrough/agent/.

Der ausführliche, erzählerische Durchlauf liegt weiterhin in scripts/demo_walkthrough.py.

Voraussetzung: API (make run-api, :8000, LLM_MODE=mock) und Vite (make ui, :5173) laufen.
Aufruf:  python scripts/ui_check/agent_check.py
Exit-Code 0 nur bei 0 Konsolenfehlern und erreichter Freigabekarte.
"""

from __future__ import annotations

import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5173"
OUT = pathlib.Path("docs/demo_walkthrough/agent")
GATE = "Freigabe erforderlich – der Agent empfiehlt"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    shots: list[tuple[str, str]] = []
    problems: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={"width": 1280, "height": 1100}).new_page()
        page.on(
            "console",
            lambda m: errors.append(f"[console.{m.type}] {m.text}") if m.type == "error" else None,
        )
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))

        page.goto(BASE, wait_until="networkidle")
        page.get_by_role("button", name="Agent", exact=True).click()
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "01_agent_tab.png"))
        shots.append(("01_agent_tab.png", "Agent-Tab geladen (Konsole geprüft)."))

        page.get_by_role("button", name="Untersuchung starten").click()
        try:
            page.wait_for_selector(f"text={GATE}", timeout=60000)
        except Exception:
            problems.append("Freigabekarte nach Start nicht erreicht.")
        page.wait_for_timeout(400)
        judge_ok = page.get_by_test_id("judge-ok").count()
        if judge_ok == 0:
            problems.append("Keine Judge-Badges an der Beleg-Prüfung/Freigabe sichtbar.")
        page.screenshot(path=str(OUT / "02_freigabe_mit_judge.png"))
        shots.append(
            (
                "02_freigabe_mit_judge.png",
                f"Freigabe erreicht, Beleg-Prüfung sichtbar ({judge_ok} bestätigt).",
            )
        )

        browser.close()

    _write_readme(shots, errors, problems)
    print(f"Agent-Check · Console-Errors: {len(errors)} · Probleme: {len(problems)}")
    for e in errors:
        print("  KONSOLE:", e)
    for pr in problems:
        print("  PROBLEM:", pr)
    return 0 if not errors and not problems else 1


def _write_readme(shots, errors, problems) -> None:
    lines = [
        "# Agent-Tab – Browser-Check (localhost:5173)",
        "",
        f"Erzeugt mit `python scripts/ui_check/agent_check.py` bei laufender API + Vite. "
        f"Konsolenfehler: **{len(errors)}** (0 = Pflicht). Bilder gitignored (Guardian S9).",
        "",
        "## Screenshots",
        "",
    ]
    lines += [f"- **{fn}** — {cap}" for fn, cap in shots]
    lines += ["", "## Auffälligkeiten", ""]
    if errors or problems:
        lines += [f"- Konsolenfehler: {e}" for e in errors] + [f"- {p}" for p in problems]
    else:
        lines.append("- Keine. Agent-Tab lädt fehlerfrei, Beleg-Prüfung und Freigabe intakt.")
    lines.append("")
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
