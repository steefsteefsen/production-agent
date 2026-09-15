"""Demo-Bereitschaft der Vektor-Suche (Finding E).

Die Vektor-Seite der RAG-Suche darf für die Demo NICHT nur „sauber fehlschlagen" – sie MUSS
verfügbar sein. Dieser Test wird ROT, wenn `sentence-transformers` fehlt (Standard-`make install`
installiert es nicht; `make install-demo` schon), und prüft zusätzlich, dass `_vector_search` nach
dem Ingest tatsächlich Treffer liefert – nicht nur, dass der Fallback greift.

Marker `embeddings`: im Standard-pytest ausgeschlossen (braucht das Modell). Im CI-e2e-Job (der die
Demo-Umgebung abbildet) wird er ausgeführt: `pytest -m embeddings tests/test_vector_search_demo.py`.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.embeddings


def test_vektor_suche_verfuegbar_und_liefert_ergebnisse():
    from production_agent.mcp import rag_server as r

    assert r._EMBED_AVAILABLE is True, (
        "sentence-transformers fehlt – Vektor-Suche nicht verfügbar. `make install-demo` ausführen."
    )
    # Modell laden (warm) + Qdrant-Index bauen; danach muss die reine Vektor-Suche Treffer liefern.
    r.ingest_docs()
    hits = r._vector_search("Folienbahn läuft schräg Siegelnaht", top_k=5)
    assert hits, "Vektor-Suche liefert keine Ergebnisse trotz installierter Dependency"

    # und der API-Kontrakt meldet die Verfügbarkeit ehrlich als True
    fused = r.search_hits("E-7001 Siegelnaht", top_k=5)
    assert fused, "Fusionssuche liefert keine Treffer"
