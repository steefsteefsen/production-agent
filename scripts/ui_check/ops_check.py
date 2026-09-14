#!/usr/bin/env python3
"""Browser-Konsolencheck für das Ops-Cockpit (localhost:8010) mit Playwright.

Dauerhaft, nicht Wegwerf: jede Änderung an der generierten Ops-UI (autopilot/ops/app.py) MUSS
hierdurch laufen, bevor sie als „fertig" gilt. HTTP 200 reicht NICHT – Pflichtbedingung ist
0 Browser-Konsolenfehler. Öffnet jeden Tab per echtem Klick, prüft im Präsentation-Tab die
Stack- und Scope-Tabelle und legt je Tab einen Screenshot nach docs/demo_walkthrough/ops/.

Voraussetzung: Ops läuft (make ops → http://localhost:8010).
Aufruf:  python scripts/ui_check/ops_check.py
Exit-Code 0 nur bei 0 Konsolenfehlern und allen sichtbaren Tabs.
"""

from __future__ import annotations

import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8010"
OUT = pathlib.Path("docs/demo_walkthrough/ops")
TABS = [
    ("Ablauf", "ablauf"),
    ("Stand", "stand"),
    ("Konfiguration", "config"),
    ("Präsentation", "presentation"),
]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    shots: list[tuple[str, str]] = []
    problems: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
        page.on(
            "console",
            lambda m: errors.append(f"[console.{m.type}] {m.text}") if m.type == "error" else None,
        )
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
        puts: list[int] = []
        page.on(
            "response",
            lambda r: (
                puts.append(r.status)
                if (r.request.method == "PUT" and "/api/config" in r.url)
                else None
            ),
        )

        page.goto(BASE, wait_until="networkidle")
        page.wait_for_timeout(400)

        # showTab muss existieren (Beweis, dass das <script> geparst wurde)
        show_tab_ok = page.evaluate("typeof showTab === 'function'")
        if not show_tab_ok:
            problems.append("showTab ist NICHT definiert – das <script> ist gebrochen.")

        for label, key in TABS:
            page.get_by_role("button", name=label, exact=True).click()
            page.wait_for_timeout(500)
            panel = page.query_selector(f"#panel-{key}")
            visible = panel.is_visible() if panel else False
            if not visible:
                problems.append(f'Tab „{label}" (#panel-{key}) nicht sichtbar nach Klick.')
            n = TABS.index((label, key)) + 1
            page.screenshot(path=str(OUT / f"{n:02d}_{key}.png"))
            shots.append((f"{n:02d}_{key}.png", f'Ops-Tab „{label}" geöffnet.'))

        # Konfiguration: „Speichern" muss ein PUT /api/config auslösen (der zuvor stumme Bug:
        # JSON.stringify(key) im doppelt-gequoteten onclick brach das Attribut → kein PUT).
        page.get_by_role("button", name="Konfiguration", exact=True).click()
        page.wait_for_timeout(500)
        save = page.get_by_role("button", name="Speichern")
        if save.count() == 0:
            problems.append("Konfiguration: kein Speichern-Button gefunden.")
        else:
            save.first.click()
            page.wait_for_timeout(900)
            if not any(s == 200 for s in puts):
                problems.append("Config-Speichern löste kein erfolgreiches PUT /api/config aus.")
            page.screenshot(path=str(OUT / "06_config_speichern.png"))
            shots.append(
                ("06_config_speichern.png", "Konfiguration: Speichern löst PUT /api/config aus.")
            )

        # Präsentation-Tab: Stack- und Scope-Tabelle im iframe prüfen
        page.get_by_role("button", name="Präsentation", exact=True).click()
        page.wait_for_timeout(800)
        stack_ok = scope_ok = False
        try:
            frame = page.frame_locator("#pres-frame")
            # In den Präsentations-Tab „Technologie-Entscheidungen" navigieren (auf Laden warten)
            tech = frame.get_by_role("button", name="Technologie-Entscheidungen")
            tech.wait_for(state="visible", timeout=8000)
            tech.click()
            # panel-scoped, damit nicht die (versteckte) Commit-Zeile im Ablauf-Tab matcht
            frame.locator("#panel-technik").get_by_text("keine Behauptung ohne Beleg").wait_for(
                state="visible", timeout=5000
            )
            stack_ok = True
            scope = frame.get_by_role("button", name="Scope-Entscheidungen")
            scope.click()
            frame.locator("#panel-scope").get_by_text("Kein ML-Training").wait_for(
                state="visible", timeout=5000
            )
            scope_ok = True
        except Exception as e:  # pragma: no cover - defensiv
            problems.append(f"Präsentations-iframe nicht prüfbar: {e}")
        if not stack_ok:
            problems.append(
                "Stack-Tabelle (Technologie-Entscheidungen) im Präsentation-Tab nicht sichtbar."
            )
        if not scope_ok:
            problems.append("Scope-Abschnitt im Präsentation-Tab nicht sichtbar.")
        page.screenshot(path=str(OUT / "05_presentation_stack.png"))
        shots.append(
            (
                "05_presentation_stack.png",
                "Präsentation-Tab: Stack-Tabelle und Scope sichtbar (im iframe).",
            )
        )

        browser.close()

    _write_readme(shots, errors, problems)
    print(
        f"Ops-Check · Console-Errors: {len(errors)} · Probleme: {len(problems)} · Screenshots: {len(shots)}"
    )
    if errors:
        print("KONSOLENFEHLER:")
        for e in errors:
            print("  -", e)
    for pr in problems:
        print("  PROBLEM:", pr)
    # Pflicht: 0 Konsolenfehler UND keine Probleme
    return 0 if not errors and not problems else 1


def _write_readme(shots, errors, problems) -> None:
    lines = [
        "# Ops-Cockpit – Browser-Check (localhost:8010)",
        "",
        f"Erzeugt mit `python scripts/ui_check/ops_check.py` bei laufendem Ops (`make ops`). "
        f"Konsolenfehler: **{len(errors)}** (0 = Pflicht). Bilder sind lokale Artefakte (Guardian S9, gitignored).",
        "",
        "## Screenshots",
        "",
    ]
    lines += [f"- **{fn}** — {cap}" for fn, cap in shots]
    lines += ["", "## Auffälligkeiten", ""]
    if errors or problems:
        lines += [f"- Konsolenfehler: {e}" for e in errors]
        lines += [f"- {p}" for p in problems]
    else:
        lines.append(
            "- Keine. Alle vier Tabs laden fehlerfrei, showTab ist definiert, Stack- und Scope-Tabelle sichtbar."
        )
    lines.append("")
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
