"""FastAPI: Health und Freigabe-Endpunkt."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(replay_env, monkeypatch):
    import importlib

    # Tests nutzen den schnellen In-Process-Pfad, nicht das echte MCP-Protokoll (keine
    # stdio-Subprozesse beim Import). Der Demo-Default in server.py bleibt Protokoll; nur diese
    # ausdrückliche Variable schaltet zurück (siehe server.py-Kommentar, ADR-0005).
    monkeypatch.setenv("MCP_VIA_PROTOCOL", "0")

    from production_agent.api import server

    importlib.reload(server)
    return TestClient(server.app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["ok"] is True


def test_approve_unknown_thread_does_not_crash_falsification(client):
    """Falsifikation: Freigabe auf unbekannten Thread darf keinen 500er werfen, sondern sauber scheitern."""
    r = client.post(
        "/investigations/approve", json={"thread_id": "gibt-es-nicht", "approved": True}
    )
    assert r.status_code in (400, 404, 409, 422)


def test_post_run_eval_reason_hit_verification(client, monkeypatch):
    """Verifikation: bei bekanntem Gold liefert die Eval reason_hit und zählt die belegten Maßnahmen."""
    from types import SimpleNamespace

    from production_agent.api import server

    monkeypatch.setattr(
        server,
        "_replay_case",
        lambda eid: SimpleNamespace(truth={"reason_code": "HDF", "duration_min": 20}),
    )
    state = {
        "hypothesis": {"reason_code": "HDF"},
        "impact": {"expected_downtime_min": 22},
        "actions": [{"rationale": "Vorfall 12"}, {"title": "ohne Beleg"}],
    }
    ev = server._post_run_eval(360, state)
    assert ev is not None
    assert ev["reason_hit"] is True
    assert ev["reason_code_gold"] == "HDF"
    assert ev["supported_actions"] == 1 and ev["total_actions"] == 2


def test_post_run_eval_none_or_miss_falsification(client, monkeypatch):
    """Falsifikation: ohne event_id oder ohne Gold-Zeile gibt es keine Eval (nichts raten);
    eine abweichende Ursache darf niemals als Treffer gewertet werden."""
    from types import SimpleNamespace

    from production_agent.api import server

    # kein event_id → None
    assert server._post_run_eval(None, {"hypothesis": {"reason_code": "HDF"}}) is None
    # event_id ohne Gold-Zeile → None
    monkeypatch.setattr(server, "_replay_case", lambda eid: None)
    assert server._post_run_eval(999, {"hypothesis": {"reason_code": "HDF"}}) is None
    # abweichende Ursache → reason_hit False, nicht True
    monkeypatch.setattr(
        server,
        "_replay_case",
        lambda eid: SimpleNamespace(truth={"reason_code": "PWF", "duration_min": 10}),
    )
    ev = server._post_run_eval(
        360, {"hypothesis": {"reason_code": "HDF"}, "impact": {}, "actions": []}
    )
    assert ev is not None and ev["reason_hit"] is False


def test_pace_seconds_verification(client):
    """Verifikation: delay_ms wird in Sekunden umgerechnet."""
    from production_agent.api import server

    assert server._pace_seconds(0) == 0
    assert server._pace_seconds(500) == 0.5


def test_pace_seconds_clamps_falsification(client):
    """Falsifikation: negative oder überzogene Werte dürfen nicht ungedeckelt durchschlagen."""
    from production_agent.api import server

    assert server._pace_seconds(-100) == 0
    assert server._pace_seconds(999999) == 2.0
