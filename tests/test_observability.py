"""Prozesslokale Live-Sicht (MCP-/Sicherheit-Tab): Werkzeugaufrufe und Guard-Entscheidungen.

Verifikation: reset leert, record_* füllt, snapshot liefert eine unabhängige Kopie.
Falsifikation: snapshot ist eine Kopie – nachträgliches Mutieren verändert den internen Zustand nicht.
"""

from __future__ import annotations

from production_agent import observability as obs


def test_reset_record_snapshot():
    obs.reset()
    assert obs.snapshot() == {"tools": [], "security": []}
    obs.record_tool_call("mes", "get_line_status", {"line_id": "L1"}, {"equipment": 7})
    obs.record_security("sql_guard", True, "SELECT erlaubt")
    obs.record_security("sql_guard", False, "DROP blockiert")
    snap = obs.snapshot()
    assert len(snap["tools"]) == 1
    assert snap["tools"][0]["server"] == "mes" and snap["tools"][0]["tool"] == "get_line_status"
    assert [s["allowed"] for s in snap["security"]] == [True, False]
    assert all("ts" in t for t in snap["tools"])  # Zeitstempel je Eintrag


def test_snapshot_ist_kopie_falsifikation():
    obs.reset()
    obs.record_tool_call("mes", "x", {}, {})
    snap = obs.snapshot()
    snap["tools"].append({"gefälscht": True})  # externe Mutation
    assert len(obs.snapshot()["tools"]) == 1  # interner Zustand unberührt
