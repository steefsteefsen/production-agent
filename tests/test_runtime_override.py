"""Config-Override aus dem Ops-Cockpit wird gespeichert UND genutzt.

Verifikation: eine im Cockpit gespeicherte Konfidenzschwelle (config/runtime.yaml) wird vom
Graph-Pfad frisch gelesen (config.runtime_value) und wirkt in der action_policy. Falsifikation:
ohne Override greift der Default, die Unter-Schwelle-Notiz erscheint NICHT.
"""

import pytest
from fastapi.testclient import TestClient

from production_agent import config as cfg
from production_agent.security.action_policy import RecommendedAction, apply_policy

# bewusst eine eingreifende Maßnahme (approval_required, nicht inform), damit die Schwelle greift
_ACTION = {
    "title": "Betroffene Station prüfen und wieder freigeben",
    "description": "Sichtprüfung, Wiederanlauf",
    "confidence": 0.70,
}


@pytest.fixture
def ops_client(tmp_path, monkeypatch):
    rt = tmp_path / "runtime.yaml"
    monkeypatch.setattr(cfg, "RUNTIME_YAML", rt)  # der Graph-Pfad liest hier
    from autopilot.ops import app as ops_app

    monkeypatch.setattr(ops_app, "RUNTIME_YAML", rt)  # das Cockpit schreibt hier – dieselbe Datei
    monkeypatch.setattr(ops_app, "AUDIT_LOG", tmp_path / "audit.jsonl")
    return TestClient(ops_app.app), rt


def test_schwelle_gespeichert_und_genutzt_verification(ops_client):
    client, rt = ops_client
    # 1. Speichern über das Cockpit-API
    r = client.put("/api/config", json={"field": "konfidenz.schwelle_empfehlung", "value": 0.85})
    assert r.status_code == 200 and r.json()["new"] == 0.85
    assert rt.exists()  # persistiert in runtime.yaml
    # 2. GENUTZT: derselbe Override wird vom Graph-Pfad frisch gelesen
    assert cfg.runtime_value("konfidenz.schwelle_empfehlung", 0.60) == 0.85
    # 3. Wirkung: Konfidenz 0.70 liegt jetzt unter der gespeicherten Schwelle 0.85 → Unter-Schwelle-Notiz
    used = apply_policy(
        [RecommendedAction(**_ACTION)],
        cfg.runtime_value("konfidenz.schwelle_empfehlung", 0.60),
    )
    assert any("unter Schwelle 0.85" in n for n in used[0].policy_notes)


def test_ohne_override_default_greift_falsification(ops_client):
    _client, _rt = ops_client  # kein Save → runtime.yaml existiert nicht
    assert cfg.runtime_value("konfidenz.schwelle_empfehlung", 0.60) == 0.60
    used = apply_policy(
        [RecommendedAction(**_ACTION)],
        cfg.runtime_value("konfidenz.schwelle_empfehlung", 0.60),
    )
    # 0.70 >= 0.60 → KEINE Unter-Schwelle-Notiz
    assert not any("unter Schwelle" in n for n in used[0].policy_notes)
