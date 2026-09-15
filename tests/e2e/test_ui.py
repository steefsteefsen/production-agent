"""E2E-Smoke-Tests für das React-Cockpit (Playwright).

Voraussetzungen:
  - BASE_URL muss gesetzt sein (z. B. http://localhost:5173)
  - pip install -e ".[e2e]" && playwright install chromium
  - Aufruf: make e2e   oder   pytest -q -m e2e tests/e2e

Ohne BASE_URL werden alle Tests übersprungen.
"""

import os

import pytest

pytestmark = pytest.mark.e2e

_BASE_URL = os.environ.get("BASE_URL", "")


@pytest.fixture(autouse=True)
def _require_base_url():
    if not _BASE_URL:
        pytest.skip("BASE_URL nicht gesetzt – E2E übersprungen")


def test_startseite_laedt(page):
    """Startseite lädt ohne HTTP-Fehler."""
    response = page.goto(_BASE_URL)
    assert response is not None and response.ok, f"HTTP {response and response.status}"
    page.wait_for_load_state("networkidle")


def test_kein_js_fehler(page):
    """Keine unbehandelten JavaScript-Fehler auf der Startseite."""
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(_BASE_URL)
    page.wait_for_load_state("networkidle")
    assert not errors, f"JS-Fehler: {errors}"


def test_cockpit_element_sichtbar(page):
    """Mindestens ein sichtbares Element mit data-testid='cockpit' ist vorhanden."""
    page.goto(_BASE_URL)
    page.wait_for_load_state("networkidle")
    locator = page.locator("[data-testid='cockpit6']")
    assert locator.count() > 0, "data-testid='cockpit6' nicht gefunden"


def test_bediener_zeigt_mehrere_hypothesen(page):
    """Bediener-Tab startet selbst eine Untersuchung und zeigt am Freigabeknoten mehrere
    Ursachenhypothesen (Balkendiagramm) sowie Maßnahmenkarten mit Original-Belegtext."""
    page.goto(_BASE_URL)
    page.wait_for_load_state("networkidle")
    page.get_by_test_id("op-hero").wait_for(timeout=60_000)
    assert page.get_by_test_id("hyp-row").count() >= 2  # mehrere Kandidaten
    assert page.get_by_test_id("op-action").count() >= 1  # Maßnahmenkarte(n)
    assert page.get_by_test_id("belegtext").count() >= 1  # Original-Belegtext


def test_bediener_durchlauf_mock_freigabe(page):
    """Mock-Durchlauf über die UI: Auto-Start → Freigabeknoten erreicht → Freigeben → Abschluss.
    Prüft die SSE→UI-Kette und den Resume-Pfad end-to-end."""
    page.goto(_BASE_URL)
    page.wait_for_load_state("networkidle")
    page.get_by_test_id("op-approve").wait_for(timeout=60_000)
    page.get_by_test_id("op-approve").click()
    page.get_by_test_id("op-result").wait_for(timeout=15_000)
