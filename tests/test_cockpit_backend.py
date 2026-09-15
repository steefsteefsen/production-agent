"""Backend für das Sechs-Tab-Cockpit: mehrere Hypothesen, RRF-Rang, RAG-Einspeisung.

Verifikation: Knoten 4 liefert mehrere Kandidaten (absteigend nach Konfidenz) bis in den
Interrupt-Payload; die Suche gibt einen rrf_rank; ein eingespeister Text ist danach auffindbar.
Falsifikation: leerer Einspeisungstext wird abgelehnt (nichts erfunden).
"""

from __future__ import annotations

import json

import pytest

from production_agent.graph.mock_llm import mock_chains
from production_agent.graph.workflow import build_graph


def _tools_mit_vorfaellen():
    return {
        "get_line_status": lambda **_: json.dumps(
            [{"equipment_id": "EQ1", "packml_state": "Held", "ts": "2026-01-01 00:00:00"}]
        ),
        "get_production_plan": lambda **_: json.dumps([]),
        "get_active_alarms": lambda **_: json.dumps(
            [{"alarm_code": "E-4711", "ts": "2026-01-01 00:00:00", "priority": 1}]
        ),
        "search_maintenance_docs": lambda **_: json.dumps(
            [{"doc": "MA-02-folienwickler.md", "text": "[Folienwickler] Folienriss: Rolle prüfen."}]
        ),
        "find_similar_incidents": lambda **_: json.dumps(
            [{"event_id": 7, "reason_code": "STO-FOLIE", "duration_min": 12.0}]
        ),
        "estimate_impact": lambda **_: json.dumps(
            {"expected_downtime_min": 25.0, "cost_eur": 5000}
        ),
    }


def test_knoten4_liefert_mehrere_hypothesen_absteigend():
    g = build_graph(tools=_tools_mit_vorfaellen(), llm=mock_chains())
    last = None
    for update in g.stream(
        {"line_id": "L1", "trace": []},
        {"configurable": {"thread_id": "ck-hyps"}},
        stream_mode="updates",
    ):
        last = update
    payload = last["__interrupt__"][0].value
    hyps = payload.get("hypotheses", [])
    assert len(hyps) >= 2  # mehrere Kandidaten, nicht nur die beste
    confs = [h["confidence"] for h in hyps]
    assert confs == sorted(confs, reverse=True)  # absteigend nach Konfidenz
    assert payload["hypothesis"]["reason_code"] == hyps[0]["reason_code"]  # beste zuerst
    assert payload.get("applied_threshold") == 0.6


def test_suche_liefert_rrf_rang():
    from production_agent.mcp.rag_server import search_hits

    hits = search_hits("Folienriss Folienwickler", top_k=5)
    assert hits, "keine Treffer"
    assert hits[0]["rrf_rank"] == 1  # 1-basierter Fusionsrang
    assert [h["rrf_rank"] for h in hits] == list(range(1, len(hits) + 1))


def test_einspeisung_dann_auffindbar_und_leer_abgelehnt():
    from production_agent.mcp.rag_server import add_document, search_hits

    marker = "Kalibrierbolzen QT7 nachgezogen und Wiederanlauf bestaetigt"
    add_document(marker, source="rueckkopplung-test")
    hits = search_hits("Kalibrierbolzen QT7", top_k=5)
    assert any(marker in h["text"] for h in hits)  # im nächsten Suchlauf auffindbar
    with pytest.raises(ValueError):
        add_document("   ")  # leerer Text wird abgelehnt, nichts erfunden
