#!/usr/bin/env python3
"""Browser-Konsolencheck der eigenständigen Freigabe-Seite (localhost:5173/freigabe) mit Playwright.

Dauerhaft, nicht Wegwerf: bestätigt nach Änderungen, dass die Freigabe-Seite ohne Konsolenfehler
lädt UND der Kern intakt ist: beste Hypothese mit Konfidenzwert und Schwellenlinie, Maßnahmenkarten
je mit Policy-Badge, Konfidenzbalken (mit Schwellenmarkierung) und ORIGINAL-Belegtext aus dem
Wartungsdokument (echter Satz, nicht nur „Beleg: Vorfall X"). Pflicht: 0 Browser-Konsolenfehler.

Voraussetzung: API (:8000, LLM_MODE=mock) und Vite (:5173) laufen.
Aufruf:  python scripts/ui_check/approval_check.py
Exit-Code 0 nur bei 0 Konsolenfehlern und vollständig gerenderter Freigabe-Seite.
"""

from __future__ import annotations

import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5173/freigabe"
OUT = pathlib.Path("docs/demo_walkthrough/approval")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    shots: list[tuple[str, str]] = []
    problems: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={"width": 1280, "height": 1400}).new_page()
        page.on(
            "console",
            lambda m: errors.append(f"[console.{m.type}] {m.text}") if m.type == "error" else None,
        )
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))

        page.goto(BASE, wait_until="networkidle")
        # Seite startet selbst eine Untersuchung; die Freigabe erscheint am interrupt().
        try:
            page.get_by_test_id("best-hypothesis").wait_for(state="visible", timeout=60000)
        except Exception:
            problems.append(
                "Beste-Hypothese-Panel nach Auto-Start nicht erreicht (kein interrupt)."
            )

        # Konfidenzwert + Schwellenlinie
        if page.get_by_test_id("hypo-confidence").count() == 0:
            problems.append("Kein großer Konfidenzwert (hypo-confidence) sichtbar.")
        if page.get_by_test_id("threshold-line").count() == 0:
            problems.append("Keine Schwellenlinie (threshold-line) sichtbar.")

        # Maßnahmenkarten: Policy-Badge, Konfidenzbalken (+Schwellenmarkierung), Belegtext
        cards = page.get_by_test_id("action-card")
        if cards.count() == 0:
            problems.append("Keine Maßnahmenkarte (action-card) sichtbar.")
        if page.get_by_test_id("policy-badge").count() == 0:
            problems.append("Kein Policy-Badge sichtbar.")
        if page.get_by_test_id("threshold-marker").count() == 0:
            problems.append("Keine Schwellenmarkierung im Konfidenzbalken sichtbar.")

        # Original-Belegtext: echter Satz, nicht nur „Beleg: Vorfall X"
        belege = page.get_by_test_id("belegtext")
        if belege.count() == 0:
            problems.append("Kein Original-Belegtext (belegtext) sichtbar.")
        else:
            txt = belege.first.inner_text().strip()
            if len(txt) < 40 or txt.lower().startswith("beleg:"):
                problems.append(f"Belegtext wirkt nicht wie ein Dokumentsatz: '{txt[:60]}'")

        # niemals forbidden anzeigen
        badges = page.get_by_test_id("policy-badge")
        for i in range(badges.count()):
            lvl = badges.nth(i).get_attribute("data-level")
            if lvl == "forbidden":
                problems.append("Policy-Badge 'forbidden' wird angezeigt – verboten.")

        page.screenshot(path=str(OUT / "01_freigabe_seite.png"), full_page=True)
        shots.append(
            ("01_freigabe_seite.png", "Freigabe-Seite: beste Hypothese, Badges, Balken, Belegtext.")
        )

        browser.close()

    _write_readme(shots, errors, problems)
    print(f"Approval-Check · Console-Errors: {len(errors)} · Probleme: {len(problems)}")
    for e in errors:
        print("  KONSOLE:", e)
    for pr in problems:
        print("  PROBLEM:", pr)
    return 0 if not errors and not problems else 1


def _write_readme(shots, errors, problems) -> None:
    lines = [
        "# Freigabe-Seite – Browser-Check (localhost:5173/freigabe)",
        "",
        f"Erzeugt mit `python scripts/ui_check/approval_check.py` bei laufender API + Vite. "
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
        lines.append(
            "- Keine. Freigabe-Seite lädt fehlerfrei; Konfidenz, Schwelle, Badges und Belegtext da."
        )
    lines.append("")
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
