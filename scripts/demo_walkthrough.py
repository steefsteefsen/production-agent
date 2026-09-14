#!/usr/bin/env python3
"""Echter UI-Walkthrough des Agent-Tabs mit Playwright (Verifikation, keine Datei-Beweise).

Voraussetzung: API (Port 8000, LLM_MODE=mock) und Vite (Port 5173) laufen bereits.
Fährt zwei Läufe im echten Chromium und legt Screenshots + Video + README nach
docs/demo_walkthrough/. NUR mock – nie live.

  Lauf 1: Start (Ereignis 360) → Erzähltext wechselt je Knoten → Freigabeknoten mit Belegen
          → Freigeben → Abschluss mit reason_hit.
  Lauf 2: gleicher Fall → Ablehnen → sauberer Abbruch.

Aufruf:  python scripts/demo_walkthrough.py
"""

from __future__ import annotations

import pathlib
import time

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5173"
OUT = pathlib.Path("docs/demo_walkthrough")
GATE_TEXT = "Freigabe erforderlich – der Agent empfiehlt"

shots: list[tuple[str, str]] = []
findings: list[str] = []


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 1500},
            record_video_dir=str(OUT / "video"),
        )
        page = ctx.new_page()
        js_errors: list[str] = []
        page.on("pageerror", lambda e: js_errors.append(str(e)))

        # Demo-Takt in den SSE-Stream injizieren, damit jeder Knoten-Erzähltext sichtbar wird
        # (rein für die Aufzeichnung; die App selbst ruft den Stream ohne delay_ms auf).
        def _pace(route):
            url = route.request.url
            route.continue_(url=url + ("&" if "?" in url else "?") + "delay_ms=1000")

        page.route("**/investigations/stream*", _pace)

        def shot(name: str, caption: str) -> None:
            page.screenshot(path=str(OUT / f"{name}.png"))
            shots.append((f"{name}.png", caption))

        page.goto(BASE, wait_until="networkidle")
        page.get_by_role("button", name="Agent", exact=True).click()
        page.wait_for_timeout(300)
        shot(
            "01_agent_tab",
            "Agent-Tab geöffnet: Steuerzeile (Ereignis 360, Modus mock), "
            "Fortschrittsleiste und die sieben Schritt-Karten im Zustand wartend.",
        )

        idx = 2

        # --- Lauf 1: Freigabe ---
        page.get_by_role("button", name="Untersuchung starten").click()
        seen: list[str] = []
        deadline = time.time() + 90
        narrative = page.get_by_test_id("narrative")
        while time.time() < deadline:
            if page.get_by_text(GATE_TEXT).count() > 0:
                break
            try:
                txt = narrative.inner_text(timeout=400).strip()
            except Exception:
                txt = ""
            if txt and (not seen or seen[-1] != txt):
                seen.append(txt)
                shot(f"{idx:02d}_lauf_erzaehltext", f"Erzähltext synchron zur Karte: „{txt}“")
                idx += 1
            page.wait_for_timeout(50)

        page.wait_for_selector(f"text={GATE_TEXT}", timeout=30000)
        page.wait_for_timeout(300)
        shot(
            f"{idx:02d}_freigabeknoten",
            "Freigabeknoten erreicht: Maßnahmenliste mit Belegen (Beleg: ähnlicher Vorfall …) "
            "und Erzähltext zur Freigabe. Der Agent empfiehlt, der Mensch entscheidet.",
        )
        idx += 1

        # Belegte Knoten-Karten einzeln aufklappen (jede Karte sichtbar, mit Funktion/Ausblick)
        for label in [
            "Linienstatus & Plan",
            "Alarme analysieren",
            "Wissen abrufen",
            "Ursache eingrenzen",
            "Wirkung schätzen",
            "Maßnahmen ableiten",
        ]:
            try:
                page.get_by_text(label, exact=False).first.click()
                page.wait_for_timeout(150)
                cap = (
                    f"Schritt-Karte „{label}“ aufgeklappt: Live-Zusammenfassung, "
                    "Funktion/Ausblick-Annotation und Payload-Detail."
                )
                shot(f"{idx:02d}_karte", cap)
                idx += 1
            except Exception as e:  # pragma: no cover - defensiv
                findings.append(f"Karte „{label}“ nicht aufklappbar: {e}")

        # Freigeben
        page.get_by_role("button", name="Freigeben").click()
        page.wait_for_selector("text=Freigegeben – regulärer Abschluss", timeout=30000)
        page.wait_for_timeout(500)
        final_txt = narrative.inner_text().strip()
        shot(
            f"{idx:02d}_abschluss_freigabe",
            f"Abschluss nach Freigabe, reason_hit gegen die Gold-Wahrheit: „{final_txt}“",
        )
        idx += 1
        if "verborgene Wahrheit" not in final_txt:
            findings.append(
                "Abschlusstext ohne reason_hit-Abgleich (erwartet: verborgene Wahrheit)."
            )  # noqa: E501

        # --- Lauf 2: Ablehnung ---
        page.get_by_role("button", name="Untersuchung starten").click()
        page.wait_for_selector(f"text={GATE_TEXT}", timeout=90000)
        page.wait_for_timeout(300)
        page.get_by_role("button", name="Ablehnen").click()
        page.wait_for_selector("text=Abgelehnt", timeout=30000)
        page.wait_for_timeout(500)
        reject_txt = narrative.inner_text().strip()
        shot(
            f"{idx:02d}_abschluss_ablehnung",
            f"Zweiter Lauf, Ablehnen: sauberer Abbruch, keine Maßnahme freigegeben. „{reject_txt}“",
        )
        idx += 1

        if js_errors:
            findings.append(f"Unbehandelte JS-Fehler im Browser: {js_errors}")
        if len(seen) < 3:
            findings.append(
                f"Nur {len(seen)} unterschiedliche Erzähltexte live erfasst – der Mock-Lauf ist "
                "sehr schnell; die Karten-Detailscreenshots belegen jeden Schritt zusätzlich."
            )

        ctx.close()
        browser.close()

    _write_readme()
    print(f"Screenshots: {len(shots)} · Auffälligkeiten: {len(findings)}")
    return 0


def _write_readme() -> None:
    lines = [
        "# UI-Walkthrough Agent-Tab (Mock)",
        "",
        "Echter Browser-Durchlauf (Playwright, Chromium, LLM_MODE=mock) des Agent-Tabs: ",
        "laufbegleitender Erzähltext je Knoten, Freigabe- und Ablehnungspfad. Erzeugt mit ",
        "`python scripts/demo_walkthrough.py` bei laufender API (8000) und Vite (5173). ",
        "Die Bilddateien und das Video sind lokale Verifikationsartefakte (per .gitignore nicht ",
        "committet – Guardian S9 lässt Binärdateien nur unter docs/status/ oder docs/images/ zu).",
        "",
        "## Screenshots",
        "",
    ]
    for fn, cap in shots:
        lines.append(f"- **{fn}** — {cap}")
    lines.append("")
    lines.append("## Auffälligkeiten")
    lines.append("")
    if findings:
        lines += [f"- {f}" for f in findings]
    else:
        lines.append(
            "- Keine. Jede Schrittkarte erschien, der Erzähltext wechselte synchron, "
            "Freigabe- und Ablehnungspfad reagierten wie erwartet."
        )
    lines.append("")
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
