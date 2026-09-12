"""Abnahmetest WP2b – Spezifikation aus docs/test_cases.md. Unveränderbar (Guardian K7).

Übersprungen, solange WP2b nicht gebaut ist (kein xfail). Sobald das Kern-Artefakt existiert, laufen
die Fälle und der Builder muss sie grün machen (gate_no_skip.py verlangt 0 Skips)."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "tests/test_rag.py"
pytestmark = pytest.mark.skipif(not ARTIFACT.exists(), reason="WP2b noch nicht gebaut")


def test_wp2b_kernartefakt_vorhanden():
    # Verifikation: das in plan.yaml/tasks.yaml zugesagte Kern-Artefakt existiert
    assert ARTIFACT.exists()


def test_wp2b_artefakt_nicht_leer_falsification():
    # Falsifikation: ein leeres Artefakt zählt nicht als erfüllt
    assert ARTIFACT.stat().st_size > 0
