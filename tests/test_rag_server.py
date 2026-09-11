"""RAG-Server: RRF-Fusion und BM25-Grundfunktion – ohne Vektorseite (WP2b)."""

from production_agent.mcp.rag_server import rrf


def test_rrf_prefers_items_ranked_in_both_lists():
    assert rrf([[1, 2, 3], [2, 5, 1]])[0] == 2


def test_rrf_single_list_is_identity_falsification():
    """Falsifikation: mit nur einer Liste darf RRF die Reihenfolge nicht umdrehen."""
    assert rrf([[7, 3, 9]]) == [7, 3, 9]
