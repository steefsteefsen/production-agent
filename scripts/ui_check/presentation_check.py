#!/usr/bin/env python3
"""Browser-Konsolencheck der geführten Präsentation (localhost:5173/presentation) mit Playwright.

Dauerhaft: die Präsentation ist EINE Quelle (direkt auf :5173 UND per iframe im Ops-Cockpit).
Pflichtbedingung: 0 Browser-Konsolenfehler. Prüft: Intro mit echten Live-Daten (Linienstatus),
Navigation durch alle Sektionen, Scope- und Stack-Tabelle sichtbar. Screenshots nach
docs/demo_walkthrough/presentation/.

Voraussetzung: API (:8000, LLM_MODE=mock) und Vite (:5173) laufen.
Aufruf:  python scripts/ui_check/presentation_check.py
Exit-Code 0 nur bei 0 Konsolenfehlern und allen sichtbaren Sektionen.
"""

from __future__ import annotations

import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5173/presentation"
OUT = pathlib.Path("docs/demo_walkthrough/presentation")
SECTIONS = ["1. Ausgangslage", "2. Datenbasis", "3. Agent-Untersuchung", "4. Scope", "5. Stack", "6. Abschluss"]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    problems: list[str] = []
    shots: list[tuple[str, str]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={"width": 1280, "height": 1000}).new_page()
        page.on("console", lambda m: errors.append(f"[console.{m.type}] {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))

        page.goto(BASE, wait_until="networkidle")
        try:
            page.get_by_test_id("presentation").wait_for(state="visible", timeout=8000)
        except Exception:
            problems.append("Präsentationsansicht (data-testid=presentation) nicht geladen.")

        # Intro: echte Live-Daten (Linienname / Stationen), nicht leer, kein 'undefined'
        page.wait_for_timeout(1200)
        intro = page.locator("main").inner_text()
        if "undefined" in intro.lower():
            problems.append("Intro enthält 'undefined'.")
        if not any(c.isdigit() for c in intro):
            problems.append("Intro ohne Live-Zahl (keine echten Daten?).")

        for idx, label in enumerate(SECTIONS, start=1):
            page.get_by_role("button", name=label).click()
            page.wait_for_timeout(400)
            page.screenshot(path=str(OUT / f"{idx:02d}_{label.split('. ')[1].lower()}.png"))
            shots.append((f"{idx:02d}_{label.split('. ')[1].lower()}.png", f"Sektion {label}."))

        # Scope- und Stack-Tabelle sichtbar
        page.get_by_role("button", name="5. Stack").click()
        page.wait_for_timeout(300)
        if page.get_by_text("keine Behauptung ohne Beleg").count() == 0:
            problems.append("Stack-Tabelle (Anker) nicht sichtbar.")
        page.get_by_role("button", name="4. Scope").click()
        page.wait_for_timeout(300)
        if page.get_by_text("Kein ML-Training").count() == 0:
            problems.append("Scope-Tabelle nicht sichtbar.")

        browser.close()

    _write_readme(shots, errors, problems)
    print(f"Presentation-Check · Console-Errors: {len(errors)} · Probleme: {len(problems)}")
    for e in errors:
        print("  KONSOLE:", e)
    for pr in problems:
        print("  PROBLEM:", pr)
    return 0 if not errors and not problems else 1


def _write_readme(shots, errors, problems) -> None:
    lines = [
        "# Geführte Präsentation – Browser-Check (localhost:5173/presentation)",
        "",
        f"Erzeugt mit `python scripts/ui_check/presentation_check.py`. Konsolenfehler: **{len(errors)}** "
        f"(0 = Pflicht). Bilder gitignored (Guardian S9). Dieselbe Ansicht wird im Ops-Cockpit per iframe "
        f"eingebettet (siehe ops_check.py).",
        "",
        "## Screenshots",
        "",
    ]
    lines += [f"- **{fn}** — {cap}" for fn, cap in shots]
    lines += ["", "## Auffälligkeiten", ""]
    if errors or problems:
        lines += [f"- Konsolenfehler: {e}" for e in errors] + [f"- {p}" for p in problems]
    else:
        lines.append("- Keine. Alle Sektionen navigierbar, Intro mit Live-Daten, Scope- und Stack-Tabelle sichtbar.")
    lines.append("")
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
