"""MCP-Server 2: RAG über simulierte Wartungsdokumente (hybride Suche: BM25 + Vektor, RRF).

Vektorseite: Qdrant lokal (data/qdrant), Modell intfloat/multilingual-e5-small.
Ingest: python -m production_agent.mcp.rag_server --ingest
Start:  python -m production_agent.mcp.rag_server  (stdio-Transport)
"""

from __future__ import annotations

import json
import re
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
QDRANT_PATH = "data/qdrant"
EMBED_MODEL = "intfloat/multilingual-e5-small"
_COLLECTION = "maintenance_docs"
_CODE_RE = re.compile(r"\b[EWI]-\d{4}\b")

try:
    from sentence_transformers import SentenceTransformer  # noqa: F401

    _EMBED_AVAILABLE = True
except ImportError:
    _EMBED_AVAILABLE = False

_embed_model: object = None  # SentenceTransformer, lazy-geladen


def _get_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer

        _embed_model = SentenceTransformer(EMBED_MODEL)
    return _embed_model  # type: ignore[return-value]


def _load_chunks() -> list[dict[str, str]]:
    """Absatzweises Chunking; Nicht-Überschrift-Absätze erhalten Überschrift-Präfix."""
    chunks: list[dict[str, str]] = []
    for p in sorted(DOC_DIR.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        current_heading = ""
        for para in (x.strip() for x in text.split("\n\n") if x.strip()):
            first_line = para.split("\n")[0]
            if first_line.startswith("#"):
                current_heading = first_line.lstrip("# ").strip()
                chunk_text = para
            else:
                chunk_text = f"[{current_heading}] {para}" if current_heading else para
            chunks.append(
                {
                    "doc": p.name,
                    "chunk_id": f"{p.stem}#{len(chunks)}",
                    "text": chunk_text,
                    "idx": len(chunks),
                }
            )
    return chunks


RUNTIME_DOCS = DOC_DIR.parent / "rag_runtime.jsonl"  # zur Laufzeit eingespeiste Belege (gitignored)


def _load_runtime_chunks() -> list[dict]:
    """Zur Laufzeit eingespeiste Dokumente (Bediener-Rückkopplung) aus der JSONL nachladen."""
    if not RUNTIME_DOCS.exists():
        return []
    out: list[dict] = []
    for line in RUNTIME_DOCS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


_CHUNKS = _load_chunks() + _load_runtime_chunks()
_BM25 = BM25Okapi([c["text"].lower().split() for c in _CHUNKS]) if _CHUNKS else None


def add_document(text: str, source: str = "rueckkopplung") -> dict:
    """Einen freigegebenen Rückkopplungstext in den RAG-Bestand einspeisen (Phase 2c).

    Hängt den Chunk in-process an, baut den BM25-Index neu (im nächsten Suchlauf sofort auffindbar)
    UND persistiert ihn in RUNTIME_DOCS, damit er einen Neustart überlebt. Kein Ersatz für den
    kuratierten Dokumentbestand – die Herkunft (source) bleibt erkennbar."""
    global _BM25
    text = (text or "").strip()
    if not text:
        raise ValueError("Leerer Belegtext – nichts einzuspeisen")
    idx = len(_CHUNKS)
    chunk = {"doc": source, "chunk_id": f"{source}#{idx}", "text": text, "idx": idx}
    _CHUNKS.append(chunk)
    _BM25 = BM25Okapi([c["text"].lower().split() for c in _CHUNKS])
    RUNTIME_DOCS.parent.mkdir(parents=True, exist_ok=True)
    with RUNTIME_DOCS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(chunk, ensure_ascii=False) + "\n")
    return chunk


def document_inventory() -> dict:
    """Übersicht des indizierten Bestands (RAG-Tab): Dokumente je Quelle + Laufzeit-Belege."""
    from collections import Counter

    by_doc = Counter(c.get("doc", "?") for c in _CHUNKS)
    runtime = [c for c in _CHUNKS if c.get("doc", "").startswith("rueckkopplung")]
    return {
        "total_chunks": len(_CHUNKS),
        "documents": sorted(by_doc.items()),
        "runtime_count": len(runtime),
    }


def rrf(rankings: list[list[int]], k: int = 60) -> list[int]:
    """Reciprocal Rank Fusion über Index-Ranglisten."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking, start=1):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=scores.get, reverse=True)  # type: ignore[arg-type]


def _vector_search(query: str, top_k: int = 20) -> list[int]:
    """Vektorsuche in Qdrant; gibt Chunk-Indizes zurück (leer wenn nicht verfügbar oder Fehler)."""
    if not _EMBED_AVAILABLE:
        return []
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(path=QDRANT_PATH)
        vec = _get_model().encode([query], normalize_embeddings=True)[0].tolist()
        results = client.search(
            collection_name=_COLLECTION,
            query_vector=vec,
            limit=top_k,
        )
        return [r.id for r in results]
    except Exception:
        return []


def ingest_docs(chunks: list[dict] | None = None) -> None:
    """Vektoreinbettungen für Chunks erstellen und in lokalem Qdrant speichern.

    Args:
        chunks: Chunk-Liste; None verwendet die beim Modulstart geladenen _CHUNKS.

    Raises:
        RuntimeError: sentence-transformers nicht installiert.
        ValueError: Keine Chunks vorhanden.
    """
    if not _EMBED_AVAILABLE:
        raise RuntimeError(
            "sentence-transformers fehlt: pip install 'production-agent[embeddings]'"
        )
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, PointStruct, VectorParams

    target = chunks if chunks is not None else _CHUNKS
    if not target:
        raise ValueError("Keine Chunks zum Ingest vorhanden")

    texts = [c["text"] for c in target]
    embeddings = _get_model().encode(texts, normalize_embeddings=True, show_progress_bar=True)
    dim = int(embeddings.shape[1])

    client = QdrantClient(path=QDRANT_PATH)
    try:
        client.delete_collection(_COLLECTION)
    except Exception:  # noqa: BLE001, S110  # nosec B110 – Collection existiert evtl. noch nicht
        pass  # Collection existiert noch nicht – ignorieren
    client.create_collection(
        collection_name=_COLLECTION,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )
    points = [
        PointStruct(id=i, vector=embeddings[i].tolist(), payload=target[i])
        for i in range(len(target))
    ]
    client.upsert(collection_name=_COLLECTION, points=points)
    print(f"Ingest: {len(points)} Chunks in '{QDRANT_PATH}' gespeichert.")


def search_hits(query: str, top_k: int = 5) -> list[dict]:
    """Kern der Dokumentsuche: BM25 + Vektor → RRF, gibt Treffer mit rrf_rank zurück.

    Von search_maintenance_docs (MCP-Tool) UND der API (RAG-Tab) genutzt, damit beide denselben
    Rang sehen. rrf_rank = 1-basierte Position in der fusionierten Rangliste (nicht nur BM25)."""
    if not _BM25:
        return []
    k = max(1, min(top_k, 10))
    bm25_scores = _BM25.get_scores(query.lower().split())
    bm25_rank = sorted(range(len(_CHUNKS)), key=lambda i: bm25_scores[i], reverse=True)[:20]
    vector_rank = _vector_search(query, top_k=20)

    # BM25 doppelt gewichten wenn Query einen Alarmcode enthält
    rankings: list[list[int]] = [bm25_rank, bm25_rank] if _CODE_RE.search(query) else [bm25_rank]
    if vector_rank:
        rankings.append(vector_rank)

    fused = rrf(rankings)[:k]
    code_hit = bool(_CODE_RE.search(query))
    return [
        {
            **_CHUNKS[i],
            "score_bm25": round(float(bm25_scores[i]), 3),
            "rrf_rank": pos,
            "code_match": code_hit,
        }
        for pos, i in enumerate(fused, start=1)
    ]


@mcp.tool()
def search_maintenance_docs(query: str, top_k: int = 5) -> str:
    """Sucht in Wartungsanleitungen, Störungsberichten und Fehlercode-Listen.

    Nutze exakte Fehlercodes (E-####, W-####, I-####) im Query – die BM25-Suche
    trifft sie exakt; bei erkanntem Code wird BM25 doppelt gewichtet (RRF k=60).
    """
    if not _BM25:
        return sanitize_tool_result('{"error": "keine Dokumente in data/docs"}', source="rag")

    hits = search_hits(query, top_k)
    audit.record("tool_call", tool="search_maintenance_docs", query=query, hits=len(hits))
    return sanitize_tool_result(
        json.dumps(hits, ensure_ascii=False),
        max_chars=settings.max_tool_result_chars,
        source="rag",
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="RAG-Server für Wartungsdokumente (Verpackungslinie L1)"
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Vektoreinbettungen erstellen und in Qdrant speichern",
    )
    args, _ = parser.parse_known_args()

    if args.ingest:
        ingest_docs()
    else:
        mcp.run()
