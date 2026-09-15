#!/usr/bin/env python3
"""Browser-Konsolencheck des Sechs-Tab-Cockpits (localhost:5173) mit Playwright.

Dauerhaft: prüft alle sechs Tabs (Bediener, Live-Daten, MCP, Wissen/RAG, Sicherheit, Konfiguration)
mit je einem Screenshot und 0 Browser-Konsolenfehlern, plus den Bediener-Voll-Kreis:
mehrere Hypothesen sichtbar → Rückkopplung → Haiku-Vervollständigung (mock) → Übernehmen (RAG-
Einspeisung) → Freigeben. Anschließend im RAG-Tab: der eingespeiste Text ist im Bestand.

Voraussetzung: API (:8000, LLM_MODE=mock) und Vite (:5173) laufen.
Aufruf:  python scripts/ui_check/cockpit_check.py
Exit-Code 0 nur bei 0 Konsolenfehlern und allen bestandenen Prüfungen.
"""

from __future__ import annotations

import pathlib
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5173"
OUT = pathlib.Path("docs/demo_walkthrough/cockpit")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    problems: list[str] = []
    shots: list[tuple[str, str]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(viewport={"width": 1360, "height": 1500}).new_page()
        page.on(
            "console",
            lambda m: errors.append(f"[console.{m.type}] {m.text}") if m.type == "error" else None,
        )
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))

        page.goto(BASE, wait_until="networkidle")
        page.get_by_test_id("cockpit6").wait_for(state="visible", timeout=10000)

        # --- BEDIENER: bis zum Interrupt, mehrere Hypothesen ---
        try:
            page.get_by_test_id("op-hero").wait_for(state="visible", timeout=60000)
        except Exception:
            problems.append("Bediener: Hypothesen-Panel (Interrupt) nicht erreicht.")
        n_hyp = page.get_by_test_id("hyp-row").count()
        if n_hyp < 2:
            problems.append(f"Bediener: nur {n_hyp} Hypothese(n) – mehrere erwartet.")
        if page.get_by_test_id("hyp-threshold").count() == 0:
            problems.append("Bediener: keine Schwellenlinie im Balkendiagramm.")
        if page.get_by_test_id("op-action").count() == 0:
            problems.append("Bediener: keine Maßnahmenkarte.")
        if page.get_by_test_id("belegtext").count() == 0:
            problems.append("Bediener: kein Original-Belegtext in den Karten.")
        page.screenshot(path=str(OUT / "01_bediener.png"), full_page=True)
        shots.append(
            ("01_bediener.png", f"Bediener: {n_hyp} Hypothesen (Balken), Maßnahmen, Belegtext.")
        )

        # --- RÜCKKOPPLUNG: Rohtext → Haiku-Vorschlag → Übernehmen (RAG-Einspeisung) ---
        page.get_by_test_id("fb-raw").fill("Rolle neu eingespannt und Andruckrolle nachjustiert")
        page.get_by_test_id("fb-suggest").click()
        try:
            page.get_by_test_id("fb-step-2").wait_for(state="visible", timeout=20000)
        except Exception:
            problems.append("Rückkopplung: Vorschlag (fb-step-2) nicht erschienen.")
        page.screenshot(path=str(OUT / "02_rueckkopplung.png"), full_page=True)
        shots.append(
            ("02_rueckkopplung.png", "Rückkopplung: Zwei-Spalten-Vergleich roh vs. Vorschlag.")
        )
        page.get_by_test_id("fb-accept").click()
        try:
            page.get_by_test_id("fb-note").wait_for(state="visible", timeout=15000)
        except Exception:
            problems.append("Rückkopplung: Übernahme-Bestätigung (fb-note) fehlt.")
        # eigentliche Maßnahmen-Freigabe (zweiter, getrennter Schritt) – sichtbare Statusänderung
        page.get_by_test_id("op-approve").click()
        try:
            page.get_by_test_id("op-result").wait_for(state="visible", timeout=15000)
        except Exception:
            problems.append("Bediener: Freigabe-Ergebnis (op-result) fehlt.")
        if page.get_by_test_id("op-status-done").count() == 0:
            problems.append("Bediener: Kopf-Banner wechselt nach Freigabe nicht auf FREIGEGEBEN.")
        page.screenshot(path=str(OUT / "03_freigegeben.png"), full_page=True)
        shots.append(
            ("03_freigegeben.png", "Bediener: übernommen + freigegeben (sichtbarer Status).")
        )

        # --- übrige Tabs ---
        for tab, testid, label in [
            ("live", "live-tab", "Live-Daten"),
            ("mcp", "mcp-tab", "MCP"),
            ("rag", "rag-tab", "Wissen/RAG"),
            ("security", "security-tab", "Sicherheit"),
            ("config", "config-tab", "Konfiguration"),
        ]:
            page.get_by_test_id(f"tab-{tab}").click()
            try:
                page.get_by_test_id(testid).wait_for(state="visible", timeout=10000)
            except Exception:
                problems.append(f"Tab {label}: Inhalt nicht sichtbar.")
            page.wait_for_timeout(700)
            n = {"live": 4, "mcp": 5, "rag": 6, "security": 7, "config": 8}[tab]
            page.screenshot(path=str(OUT / f"0{n}_{tab}.png"), full_page=True)
            shots.append((f"0{n}_{tab}.png", f"Tab {label}."))

        # tab-spezifische Kernprüfungen
        page.get_by_test_id("tab-live").click()
        try:
            page.get_by_test_id("live-station").first.wait_for(state="visible", timeout=8000)
        except Exception:
            pass
        page.wait_for_timeout(500)
        if page.get_by_test_id("live-station").count() < 7:
            problems.append("Live-Daten: weniger als 7 Stationen.")
        page.get_by_test_id("tab-mcp").click()
        page.wait_for_timeout(400)
        if page.get_by_test_id("server-card").count() < 3:
            problems.append("MCP: weniger als 3 Server-Karten (mes/knowledge/business_rules).")
        # Teil B: vertikale Timeline; alle Schritte aufklappen und einen Screenshot machen
        steps = page.get_by_test_id("mcp-step")
        if steps.count() < 10:
            problems.append(f"MCP: Timeline hat nur {steps.count()} Schritte (erwartet ≥10).")
        for i in range(steps.count()):
            steps.nth(i).click()
            page.wait_for_timeout(60)
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "05b_mcp_timeline.png"), full_page=True)
        shots.append(("05b_mcp_timeline.png", "MCP-Timeline: alle Schritte aufgeklappt."))
        page.get_by_test_id("tab-rag").click()
        page.wait_for_timeout(600)
        # Teil C: Landkarte (4 Gruppen), Fusions-Visualisierung, Normen-Ampel
        if page.get_by_test_id("doc-group").count() < 4:
            problems.append("RAG: Dokumentenlandkarte hat nicht 4 Gruppen.")
        if page.get_by_test_id("fusion-card").count() == 0:
            problems.append("RAG: keine Fusions-Visualisierung.")
        if page.get_by_test_id("rrf-rank").count() == 0:
            problems.append("RAG: keine rrf_rank-Fusionsrangfolge.")
        if page.get_by_test_id("rag-runtime").count() == 0:
            problems.append(
                "RAG: eingespeister Rückkopplungstext nicht im Bestand (kein Voll-Kreis)."
            )
        page.screenshot(path=str(OUT / "06b_rag_landkarte.png"), full_page=True)
        shots.append(("06b_rag_landkarte.png", "RAG: Landkarte, Fusion, Normen-Ampel."))
        page.get_by_test_id("tab-security").click()
        page.wait_for_timeout(400)
        page.get_by_test_id("kpi-security").click()
        page.wait_for_timeout(300)
        if page.get_by_test_id("sec-entry").count() == 0:
            problems.append("Sicherheit: keine Guard-Entscheidungen nach Aufklappen.")
        page.get_by_test_id("tab-config").click()
        page.wait_for_timeout(400)
        if page.get_by_test_id("slider-konfidenz.schwelle_empfehlung").count() == 0:
            problems.append("Konfiguration: kein Konfidenz-Slider.")
        if page.get_by_test_id("status-mcp").count() == 0:
            problems.append("Konfiguration: MCP-Statusanzeige (kein Toggle) fehlt.")

        browser.close()

    _write_readme(shots, errors, problems)
    print(f"Cockpit-Check · Console-Errors: {len(errors)} · Probleme: {len(problems)}")
    for e in errors:
        print("  KONSOLE:", e)
    for pr in problems:
        print("  PROBLEM:", pr)
    return 0 if not errors and not problems else 1


def _write_readme(shots, errors, problems) -> None:
    lines = [
        "# Sechs-Tab-Cockpit – Browser-Check (localhost:5173)",
        "",
        f"Erzeugt mit `python scripts/ui_check/cockpit_check.py`. Konsolenfehler: **{len(errors)}** "
        "(0 = Pflicht). Bilder gitignored (Guardian S9).",
        "",
        "## Screenshots",
        "",
    ]
    lines += [f"- **{fn}** — {cap}" for fn, cap in shots]
    lines += ["", "## Auffälligkeiten", ""]
    if errors or problems:
        lines += [f"- Konsolenfehler: {e}" for e in errors] + [f"- {p}" for p in problems]
    else:
        lines.append("- Keine. Alle sechs Tabs laden fehlerfrei; Bediener-Voll-Kreis intakt.")
    lines.append("")
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
