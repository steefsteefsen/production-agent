"""MCP-Server 2: RAG über simulierte Wartungsdokumente (hybride Suche: BM25 + Vektor, RRF).

Skelett: BM25 ist sofort lauffähig (rank-bm25). Die Vektorseite (Qdrant + offenes
Embedding-Modell) wird in Arbeitspaket WP2 ergänzt. Dokumente liegen in data/docs/*.md.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastmcp import FastMCP
from rank_bm25 import BM25Okapi

from production_agent.config import get_settings
from production_agent.security.audit import AuditLog
from production_agent.security.injection_guard import sanitize_tool_result

settings = get_settings()
audit = AuditLog(settings.audit_log_path)
mcp = FastMCP("maintenance_docs")

DOC_DIR = Path("data/docs")


def _load_chunks() -> list[dict[str, str]]:
    chunks: list[dict[str, str]] = []
    for p in sorted(DOC_DIR.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        for i, para in enumerate(x.strip() for x in text.split("\n\n") if x.strip()):
            chunks.append({"doc": p.name, "chunk_id": f"{p.stem}#{i}", "text": para})
    return chunks


_CHUNKS = _load_chunks()
_BM25 = BM25Okapi([c["text"].lower().split() for c in _CHUNKS]) if _CHUNKS else None


def rrf(rankings: list[list[int]], k: int = 60) -> list[int]:
    """Reciprocal Rank Fusion über Index-Ranglisten."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking, start=1):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=scores.get, reverse=True)  # type: ignore[arg-type]


@mcp.tool()
def search_maintenance_docs(query: str, top_k: int = 5) -> str:
    """Sucht in Wartungsanleitungen, Störungsberichten und Fehlercode-Listen.
    Nutze exakte Fehlercodes/Teilenummern im Query – die Stichwortsuche trifft sie exakt."""
    if not _BM25:
        return sanitize_tool_result('{"error": "keine Dokumente in data/docs"}', source="rag")
    bm25_scores = _BM25.get_scores(query.lower().split())
    bm25_rank = sorted(range(len(_CHUNKS)), key=lambda i: bm25_scores[i], reverse=True)[:20]
    vector_rank: list[int] = []  # WP2: Qdrant-Treffer hier einfügen
    fused = rrf([bm25_rank, vector_rank] if vector_rank else [bm25_rank])[: max(1, min(top_k, 10))]
    hits = [{**_CHUNKS[i], "score_bm25": round(float(bm25_scores[i]), 3)} for i in fused]
    audit.record("tool_call", tool="search_maintenance_docs", query=query, hits=len(hits))
    return sanitize_tool_result(
        json.dumps(hits, ensure_ascii=False), max_chars=settings.max_tool_result_chars, source="rag"
    )


if __name__ == "__main__":
    mcp.run()
