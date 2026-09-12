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
    locator = page.locator("[data-testid='cockpit']")
    assert locator.count() > 0, "data-testid='cockpit' nicht gefunden"
