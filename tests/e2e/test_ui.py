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


def _open_agent_tab(page):
    page.goto(_BASE_URL)
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name="Agent", exact=True).click()


def test_agent_tab_zeigt_gefuehrte_schritte(page):
    """Agent-Tab rendert die acht Knoten-Schritte (inkl. Beleg-Prüfung), den Start-Knopf und den
    Demo-Notizen-Umschalter (statisch, ohne Lauf)."""
    _open_agent_tab(page)
    assert page.get_by_role("button", name="Untersuchung starten").is_visible()
    assert page.get_by_text("1 · Linienstatus & Plan").is_visible()
    assert page.get_by_text("7 · Beleg-Prüfung", exact=True).is_visible()
    assert page.get_by_text("8 · Freigabe", exact=True).is_visible()
    assert page.get_by_text("Demo-Notizen", exact=False).is_visible()
    # Präsentationsmodus: eine Funktion-Annotation ist sichtbar
    assert page.get_by_text("Funktion:", exact=False).first.is_visible()


def test_agent_durchlauf_mock_freigabe(page):
    """Mock-Durchlauf über die UI: Start → Karten füllen sich → Freigabe erforderlich → Freigeben
    → Abschluss. Prüft die SSE→Karten-Kette und den Resume-Pfad end-to-end."""
    _open_agent_tab(page)
    page.get_by_role("button", name="Untersuchung starten").click()
    # Der Freigabeknoten (interrupt) muss erreicht werden – beweist, dass der SSE-Stream Karten füllt.
    page.get_by_text("Freigabe erforderlich", exact=False).first.wait_for(timeout=30_000)
    page.get_by_role("button", name="Freigeben").click()
    page.get_by_text("regulärer Abschluss", exact=False).wait_for(timeout=15_000)
