"""tests/test_ops.py – Ops-Cockpit: Verifikation und Falsifikation.

Verifikation:
  - GET /  liefert HTML mit allen vier Tab-Labels
  - GET /api/state gibt Lanes-Struktur zurück
  - GET /api/config zeigt die konfigurierbaren Felder
  - PUT /api/config schreibt runtime.yaml + Audit-Zeile

Falsifikation:
  - PUT auf nicht-konfigurierbares Feld → 403
  - decisions.yaml bleibt byte-identisch nach PUT
  - Aktion mit unbekanntem WP → 404
"""

from __future__ import annotations

import json
from pathlib import Path

import autopilot.ops.app as ops_app
import pytest
import yaml
from autopilot.ops.app import app
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def patched_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Leitet runtime.yaml und Audit-Log in ein temporäres Verzeichnis um."""
    rt = tmp_path / "runtime.yaml"
    audit = tmp_path / "ops_audit.jsonl"
    monkeypatch.setattr(ops_app, "RUNTIME_YAML", rt)
    monkeypatch.setattr(ops_app, "AUDIT_LOG", audit)
    return rt, audit


# ---------------------------------------------------------------------------
# Verifikation
# ---------------------------------------------------------------------------


def test_get_root_hat_alle_tabs(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text
    for label in ("Ablauf", "Stand", "Konfiguration", "Präsentation"):
        assert label in html, f"Tab '{label}' fehlt im HTML"


def test_api_state_liefert_lanes(client: TestClient) -> None:
    resp = client.get("/api/state")
    assert resp.status_code == 200
    data = resp.json()
    assert "lanes" in data
    # mindestens eine Lane mit packages-Liste
    lanes = data["lanes"]
    assert isinstance(lanes, dict)
    assert len(lanes) > 0
    first_lane = next(iter(lanes.values()))
    assert "packages" in first_lane
    assert isinstance(first_lane["packages"], list)


def test_api_config_zeigt_konfigurierbare_felder(client: TestClient) -> None:
    resp = client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "alarm_prioritaet.verfahren" in data
    assert "audit.personenbezug" in data
    assert "konfidenz.schwelle_empfehlung" in data
    # alle müssen configurable: true tragen
    for key in (
        "alarm_prioritaet.verfahren",
        "audit.personenbezug",
        "konfidenz.schwelle_empfehlung",
    ):
        assert data[key]["configurable"] is True, f"{key} sollte configurable sein"


def test_put_config_schreibt_runtime_yaml_und_audit(
    client: TestClient, patched_paths: tuple[Path, Path]
) -> None:
    rt, audit = patched_paths
    resp = client.put(
        "/api/config",
        json={"field": "alarm_prioritaet.verfahren", "value": "hersteller_severity"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["field"] == "alarm_prioritaet.verfahren"
    assert body["new"] == "hersteller_severity"

    # runtime.yaml muss existieren und den Wert enthalten
    assert rt.exists(), "runtime.yaml wurde nicht erzeugt"
    runtime = yaml.safe_load(rt.read_text(encoding="utf-8"))
    assert runtime["alarm_prioritaet"]["verfahren"] == "hersteller_severity"

    # Audit-Eintrag muss vorhanden sein
    assert audit.exists(), "ops_audit.jsonl wurde nicht erzeugt"
    entry = json.loads(audit.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert entry["field"] == "alarm_prioritaet.verfahren"
    assert entry["new"] == "hersteller_severity"
    assert entry["role"] == "Stefan"
    assert "time" in entry


def test_put_config_slider_schwelle(client: TestClient, patched_paths: tuple[Path, Path]) -> None:
    rt, audit = patched_paths
    resp = client.put(
        "/api/config",
        json={"field": "konfidenz.schwelle_empfehlung", "value": 0.75},
    )
    assert resp.status_code == 200
    runtime = yaml.safe_load(rt.read_text(encoding="utf-8"))
    assert runtime["konfidenz"]["schwelle_empfehlung"] == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# Falsifikation
# ---------------------------------------------------------------------------


def test_put_nicht_konfigurierbares_feld_liefert_403(client: TestClient) -> None:
    resp = client.put(
        "/api/config",
        json={"field": "linie.name", "value": "Andere Linie"},
    )
    assert resp.status_code == 403
    detail = resp.json().get("detail", "")
    assert "nicht konfigurierbar" in detail or "403" in str(resp.status_code)


def test_put_unbekanntes_config_feld_liefert_403(client: TestClient) -> None:
    resp = client.put(
        "/api/config",
        json={"field": "ereignis.erstalarm_fenster_s", "value": 30},
    )
    assert resp.status_code == 403


def test_decisions_yaml_bleibt_unveraendert(
    client: TestClient, patched_paths: tuple[Path, Path]
) -> None:
    before = ops_app.DECISIONS_YAML.read_bytes()
    client.put(
        "/api/config",
        json={"field": "konfidenz.schwelle_empfehlung", "value": 0.70},
    )
    after = ops_app.DECISIONS_YAML.read_bytes()
    assert before == after, "decisions.yaml wurde verändert – das ist verboten (Guardian S5)"


def test_unbekanntes_wp_retry_liefert_404(client: TestClient) -> None:
    resp = client.post("/api/actions/retry", json={"wp": "WP_UNBEKANNT_XYZ"})
    assert resp.status_code == 404
    assert "Unbekanntes Paket" in resp.json().get("detail", "")


def test_unbekanntes_wp_skip_liefert_404(client: TestClient) -> None:
    resp = client.post("/api/actions/skip", json={"wp": "DOES_NOT_EXIST"})
    assert resp.status_code == 404


def test_unbekanntes_wp_sync_liefert_404(client: TestClient) -> None:
    resp = client.post("/api/actions/sync", json={"wp": "PHANTOMPAKET"})
    assert resp.status_code == 404


def test_api_log_unbekanntes_wp_liefert_404(client: TestClient) -> None:
    resp = client.get("/api/log/NICHTVORHANDEN")
    assert resp.status_code == 404
