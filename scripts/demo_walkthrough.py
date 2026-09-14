#!/usr/bin/env python3
"""Echter UI-Walkthrough des Agent-Tabs mit Playwright (Verifikation, keine Datei-Beweise).

Voraussetzung: API (Port 8000, LLM_MODE=mock) und Vite (Port 5173) laufen bereits.
Fährt zwei Läufe im echten Chromium und legt Screenshots + Video + README nach
docs/demo_walkthrough/. NUR mock – nie live.

  Lauf A (Ereignis 360): Erzähltext wechselt je Knoten inkl. Beleg-Prüfung (LLM-as-Judge),
          alle Maßnahmen vom Judge bestätigt → Freigeben → Abschluss mit reason_hit.
  Lauf B (Ereignis 360, tamper_evidence=1): der Beleg der ersten Maßnahme wird entfernt →
          der Judge bestätigt sie NICHT; das rote Badge ist an der Beleg-Prüfung und am
          Freigabe-Gate sichtbar (der entscheidende Screenshot). Danach Ablehnen.

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
_idx = [1]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 1600},
            record_video_dir=str(OUT / "video"),
        )
        page = ctx.new_page()
        js_errors: list[str] = []
        page.on("pageerror", lambda e: js_errors.append(str(e)))
        state = {"tamper": False}

        # Demo-Takt (delay_ms) für sichtbare Knotenwechsel; in Lauf B zusätzlich tamper_evidence,
        # damit der Judge eine Maßnahme sichtbar ablehnt. Die App selbst ruft ohne beides auf.
        def _route(route):
            url = route.request.url
            sep = "&" if "?" in url else "?"
            extra = "delay_ms=1000" + ("&tamper_evidence=1" if state["tamper"] else "")
            route.continue_(url=url + sep + extra)

        page.route("**/investigations/stream*", _route)

        def shot(name: str, caption: str) -> None:
            fn = f"{_idx[0]:02d}_{name}"
            page.screenshot(path=str(OUT / f"{fn}.png"))
            shots.append((f"{fn}.png", caption))
            _idx[0] += 1

        narrative = page.get_by_test_id("narrative")

        page.goto(BASE, wait_until="networkidle")
        page.get_by_role("button", name="Agent", exact=True).click()
        page.wait_for_timeout(300)
        shot(
            "agent_tab",
            "Agent-Tab: acht Karten inkl. neuer Karte 7 „Beleg-Prüfung“ vor der Freigabe.",
        )

        # --- Lauf A: alle Maßnahmen vom Judge bestätigt ---
        page.get_by_role("button", name="Untersuchung starten").click()
        seen: list[str] = []
        deadline = time.time() + 90
        while time.time() < deadline:
            if page.get_by_text(GATE_TEXT).count() > 0:
                break
            try:
                txt = narrative.inner_text(timeout=400).strip()
            except Exception:
                txt = ""
            if txt and (not seen or seen[-1] != txt):
                seen.append(txt)
                if "unabhängiges Modell" in txt:
                    shot("lauf_belegpruefung", f"Erzähltext Beleg-Prüfung: „{txt}“")
                else:
                    shot("lauf_erzaehltext", f"Erzähltext synchron zur Karte: „{txt}“")
            page.wait_for_timeout(50)

        page.wait_for_selector(f"text={GATE_TEXT}", timeout=30000)
        page.wait_for_timeout(300)
        ok_badges = page.get_by_test_id("judge-ok").count()
        fail_badges = page.get_by_test_id("judge-fail").count()
        shot(
            "beleg_alle_gruen",
            f"Beleg-Prüfung-Karte und Freigabe-Gate: alle Maßnahmen „vom Judge bestätigt“ "
            f"({ok_badges} grün, {fail_badges} rot).",
        )
        if ok_badges == 0:
            findings.append("Lauf A: keine grünen Judge-Badges gefunden.")

        # Folien-Ansicht: Karten aufklappen → drei Blöcke Eingang · Transformation · Bewertung
        for label in ["Alarme analysieren", "Ursache eingrenzen", "Beleg-Prüfung"]:
            page.get_by_text(label, exact=False).first.click()
            page.wait_for_timeout(250)
            has_blocks = (
                page.get_by_text("Eingang", exact=True).count() > 0
                and page.get_by_text("Transformation", exact=True).count() > 0
                and page.get_by_text("Bewertung", exact=True).count() > 0
            )
            shot(
                "folie",
                f"Folie „{label}“: Eingang · Transformation · Bewertung "
                f"(warum Schritt/Werkzeug, weitere Schritte).",
            )
            if not has_blocks:
                findings.append(f"Folie „{label}“: nicht alle drei Blöcke sichtbar.")
            page.get_by_text(label, exact=False).first.click()  # wieder zuklappen
            page.wait_for_timeout(150)

        page.get_by_role("button", name="Freigeben").click()
        page.wait_for_selector("text=Freigegeben – regulärer Abschluss", timeout=30000)
        page.wait_for_timeout(400)
        shot(
            "abschluss_freigabe",
            f"Abschluss nach Freigabe (reason_hit): „{narrative.inner_text().strip()}“",
        )

        # --- Lauf B: Judge lehnt eine Maßnahme ab (manipulierter/fehlender Beleg) ---
        state["tamper"] = True
        page.get_by_role("button", name="Untersuchung starten").click()
        page.wait_for_selector(f"text={GATE_TEXT}", timeout=90000)
        page.wait_for_timeout(400)
        fail_badges_b = page.get_by_test_id("judge-fail").count()
        shot(
            "beleg_judge_lehnt_ab",
            "ENTSCHEIDEND: Beleg-Prüfung mit rotem Badge „✗ vom Judge nicht bestätigt“ – der "
            "Judge stützt eine Maßnahme ohne Beleg NICHT; das Badge ist auch am Gate sichtbar.",
        )
        if fail_badges_b == 0:
            findings.append(
                "Lauf B: KEIN rotes Judge-Badge gefunden – Ablehnungsfall nicht sichtbar (Fund!)."
            )
        # Judge-Notiz am Gate sichtbar machen
        if page.get_by_text("Judge:").count() > 0:
            shot(
                "beleg_judge_note",
                "Freigabe-Gate zeigt die Judge-Begründung zur abgelehnten Maßnahme.",
            )

        page.get_by_role("button", name="Ablehnen").click()
        page.wait_for_selector("text=Abgelehnt", timeout=30000)
        page.wait_for_timeout(400)
        shot(
            "abschluss_ablehnung",
            f"Ablehnen-Pfad: sauberer Abbruch. „{narrative.inner_text().strip()}“",
        )

        if js_errors:
            findings.append(f"Unbehandelte JS-Fehler im Browser: {js_errors}")

        ctx.close()
        browser.close()

    _write_readme()
    print(f"Screenshots: {len(shots)} · Auffälligkeiten: {len(findings)}")
    return 0


def _write_readme() -> None:
    lines = [
        "# UI-Walkthrough Agent-Tab (Mock) – LLM-as-Judge",
        "",
        "Echter Browser-Durchlauf (Playwright, Chromium, LLM_MODE=mock) des Agent-Tabs mit der neuen ",
        "Beleg-Prüfung (Knoten 7, LLM-as-Judge). Erzeugt mit `python scripts/demo_walkthrough.py` bei ",
        "laufender API (8000) und Vite (5173). Die Bilddateien und das Video sind lokale ",
        "Verifikationsartefakte (per .gitignore nicht committet – Guardian S9 lässt Binärdateien nur ",
        "unter docs/status/ oder docs/images/ zu).",
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
            "- Keine. Die Beleg-Prüfung erschien als eigener Schritt; in Lauf A bestätigte der Judge "
            "alle Maßnahmen (grün), in Lauf B lehnte er die Maßnahme mit entferntem Beleg sichtbar ab "
            "(rotes Badge am Gate)."
        )
    lines.append("")
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
