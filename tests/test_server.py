"""FastAPI: Health und Freigabe-Endpunkt."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(replay_env):
    import importlib

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
