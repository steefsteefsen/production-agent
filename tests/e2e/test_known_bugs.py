"""Regressionssuite: ein gezielter Test je HEUTE bestätigtem Bug, gegen den ECHTEN Demo-Pfad.

Zweck (Finding D): keiner dieser Bugs darf je wieder unbemerkt zurückkommen. Alle Tests laufen über
den echten Default (make run-api ohne Flags = In-Process; kein MCP_VIA_PROTOCOL-Umgehen wie beim
ursprünglichen N-1-Verstecken) gegen die laufende UI (BASE_URL) und API.

Voraussetzung: BASE_URL gesetzt (Vite :5173, Proxy → API :8000), API im echten Default gestartet.
Aufruf:  make e2e   oder   pytest -q -m e2e tests/e2e
"""

from __future__ import annotations

import json
import os

import pytest

pytestmark = pytest.mark.e2e

_BASE_URL = os.environ.get("BASE_URL", "")


@pytest.fixture(autouse=True)
def _require_base_url():
    if not _BASE_URL:
        pytest.skip("BASE_URL nicht gesetzt – E2E übersprungen")


def _api_get(page, path: str) -> dict:
    r = page.request.get(_BASE_URL + path)
    assert r.ok, f"GET {path} → {r.status}"
    return r.json()


def _api_put(page, path: str, body: dict) -> dict:
    r = page.request.put(
        _BASE_URL + path, data=json.dumps(body), headers={"Content-Type": "application/json"}
    )
    assert r.ok, f"PUT {path} → {r.status}"
    return r.json()


def _open_operator(page):
    page.goto(_BASE_URL)
    page.wait_for_load_state("networkidle")
    page.get_by_test_id("op-hero").wait_for(timeout=90_000)


# 1 — Konfidenzschwelle-Drift: 0.60 muss ZUR LAUFZEIT aktiv sein (nicht nur in der Datei).
def test_bug_konfidenzschwelle_0_60_aktiv(page):
    cfg = _api_get(page, "/api/config")
    assert cfg["konfidenzschwelle"]["value"] == 0.60, cfg["konfidenzschwelle"]
    assert cfg["drift"] is False, "runtime.yaml driftet vom decisions.yaml-Default ab"


# 2 — Freigabe zeigt SOFORT nach Klick eine sichtbare Statusänderung (grünes Kopf-Banner).
def test_bug_freigabe_sichtbare_statusaenderung(page):
    _open_operator(page)
    page.get_by_test_id("op-approve").click()
    page.get_by_test_id("op-status-done").wait_for(timeout=15_000)
    assert "FREIGEGEBEN" in page.get_by_test_id("op-status-done").inner_text()


# 3 — N-1: echter Demo-Default liefert STO-FOLIE + 5 Vorfälle + Judge bestätigt (NICHT STO-UNBEKANNT).
def test_bug_n1_echter_default_replay_zeit(page):
    _open_operator(page)
    hero = page.get_by_test_id("op-hero").inner_text()
    assert "STO-FOLIE" in hero and "STO-UNBEKANNT" not in hero, hero[:120]
    assert "5 ähnlichen Vorfällen" in hero, "nicht 5 ähnliche Vorfälle (SIM_NOW-Bug?)"
    assert page.get_by_text("vom Judge bestätigt").count() >= 1


# 4 — Finding A: Zustand nach Freigabe übersteht Tab-Wechsel (kein Auto-Neustart).
def test_bug_zustand_ueberstehet_tabwechsel(page):
    _open_operator(page)
    page.get_by_test_id("op-approve").click()
    page.get_by_test_id("op-status-done").wait_for(timeout=15_000)
    page.get_by_test_id("tab-mcp").click()
    page.wait_for_timeout(600)
    page.get_by_test_id("tab-operator").click()
    page.wait_for_timeout(1500)
    assert page.get_by_test_id("op-status-done").count() >= 1, "Zustand nach Rückkehr verloren"
    assert page.get_by_test_id("op-running").count() == 0, "Untersuchung wurde neu gestartet"


# 5 — Finding B: mindestens zwei Ereignisse auswählbar, liefern unterschiedliche korrekte Ursachen.
def test_bug_ereignis_auswahl_zwei_faelle(page):
    _open_operator(page)
    assert "STO-FOLIE" in page.get_by_test_id("op-hero").inner_text()  # 360
    page.get_by_test_id("event-select").select_option("336")
    page.get_by_test_id("op-hero").wait_for(timeout=90_000)
    page.wait_for_timeout(800)
    assert "STO-ANTRIEB" in page.get_by_test_id("op-hero").inner_text()  # 336, andere Ursache


# 6 — Finding C: keine zwei UI-Einträge der RAG-Fusionsliste sind ohne Unterscheidungsmerkmal gleich.
def test_bug_rag_fusion_keine_ununterscheidbaren_duplikate(page):
    page.goto(_BASE_URL)
    page.wait_for_load_state("networkidle")
    page.get_by_test_id("tab-rag").click()
    page.get_by_test_id("rrf-name").first.wait_for(timeout=20_000)
    names = page.get_by_test_id("rrf-name")
    texts = [names.nth(i).inner_text() for i in range(names.count())]
    assert len(texts) == len(set(texts)), f"ununterscheidbare Duplikate: {texts}"
    for t in texts:  # jeder Eintrag trägt eine Chunk-Kennung
        assert "Chunk" in t, f"Eintrag ohne Chunk-Kennung: {t[:60]}"


# 7 — Config-Save-und-genutzt: UI-Wert ändern → sofort im nächsten Lauf wirksam (dann zurücksetzen).
def test_bug_config_save_wird_genutzt(page):
    try:
        _api_put(page, "/api/config", {"field": "konfidenz.schwelle_empfehlung", "value": 0.85})
        assert _api_get(page, "/api/config")["konfidenzschwelle"]["value"] == 0.85
        page.goto(_BASE_URL)
        page.wait_for_load_state("networkidle")
        page.get_by_test_id("op-restart").click()
        page.get_by_test_id("op-hero").wait_for(timeout=90_000)
        page.wait_for_timeout(800)
        # die neue Schwelle 0.85 muss im Lauf wirken (Legende „Schwelle 0.85")
        assert "0.85" in page.get_by_test_id("op-hero").inner_text(), "0.85 nicht im Lauf wirksam"
    finally:
        _api_put(page, "/api/config", {"field": "konfidenz.schwelle_empfehlung", "value": 0.60})
