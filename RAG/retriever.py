import re
import time
from typing import Any, Dict, List, Optional
import config
from .embeddings import embed_query
from .reranker import rerank
from .text_cleaner import clean_retrieval_text
from .vector_store import get_collection

def retrieve(query: str, customer_id: int, top_k: int = config.TOP_K, metrics: Optional[Dict[str, Any]] = None) -> List[dict]:
    
    if isinstance(customer_id, bool) or not isinstance(customer_id, int) or customer_id <= 0:
        raise ValueError("customer_id must be a positive integer for tenant-scoped retrieval")

    total_start = time.perf_counter()

    # get ChromaDB collection
    start = time.perf_counter()
    collection = get_collection()
    collection_ms = (time.perf_counter() - start) * 1000

    if collection.count() == 0:
        total_ms = (time.perf_counter() - total_start) * 1000
        if metrics is not None:
            metrics.update({
                "collection_ms": collection_ms,
                "embedding_ms": 0.0,
                "search_ms": 0.0,
                "hits_ms": 0.0,
                "rerank_ms": 0.0,
                "total_ms": total_ms,
                "candidate_k": 0,
                "result_count": 0,
            })
        return []

    candidate_k = min(max(top_k, config.RERANK_CANDIDATES), collection.count())

    # generate query embedding
    start = time.perf_counter()
    query_embedding = embed_query(query)
    embedding_ms = (time.perf_counter() - start) * 1000

    # ChromaDB vector search
    start = time.perf_counter()
    results = collection.query(query_embeddings=[query_embedding], n_results=candidate_k, where={"$or": [{"scope": "global"}, {"customer": customer_id}]},)
    search_ms = (time.perf_counter() - start) * 1000

    # build hits
    start = time.perf_counter()
    hits = []
    for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
        cleaned_doc = clean_retrieval_text(doc)
        if cleaned_doc:
            hits.append({"text": cleaned_doc, "metadata": meta, "distance": dist})
    hits_ms = (time.perf_counter() - start) * 1000

    # reranking
    start = time.perf_counter()
    ranked_hits = rerank(query, hits, top_k=top_k)
    rerank_ms = (time.perf_counter() - start) * 1000

    # total retrieval time
    total_ms = (time.perf_counter() - total_start) * 1000

    # store metrics for Retrieve Agent
    if metrics is not None:
        metrics.update({
            "collection_ms": collection_ms,
            "embedding_ms": embedding_ms,
            "search_ms": search_ms,
            "hits_ms": hits_ms,
            "rerank_ms": rerank_ms,
            "total_ms": total_ms,
            "candidate_k": candidate_k,
            "result_count": len(ranked_hits)
        })

    return ranked_hits


def retrieve_results(
    query: str,
    customer_id: int,
    k_cases: int,
    k_kb: int,
) -> List[dict]:
    if isinstance(customer_id, bool) or not isinstance(customer_id, int) or customer_id <= 0:
        raise ValueError("customer_id must be a positive integer for tenant-scoped retrieval")
    for name, value in (("k_cases", k_cases), ("k_kb", k_kb)):
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
            raise ValueError(f"{name} must be an integer between 0 and 100")
    if not query.strip():
        raise ValueError("query must not be empty")
    if k_cases == 0 and k_kb == 0:
        return []

    collection = get_collection()
    collection_count = collection.count()
    if collection_count == 0:
        return []

    query_embedding = embed_query(query)
    results = []
    for is_case, limit in ((True, k_cases), (False, k_kb)):
        if limit == 0:
            continue

        where = (
            {"$and": [{"category": "incident_history"}, {"customer": customer_id}]}
            if is_case
            else {"category": {"$ne": "incident_history"}}
        )
        candidate_k = min(max(limit * 4, config.RERANK_CANDIDATES), collection_count)
        matches = collection.query(
            query_embeddings=[query_embedding],
            n_results=candidate_k,
            where=where,
        )
        ids = matches.get("ids", [[]])[0]
        documents = matches.get("documents", [[]])[0]
        metadatas = matches.get("metadatas", [[]])[0]
        hits = []
        for record_id, document, metadata in zip(ids, documents, metadatas):
            cleaned_text = clean_retrieval_text(document or "")
            if cleaned_text:
                hits.append({
                    "id": record_id,
                    "text": cleaned_text,
                    "metadata": metadata or {},
                })

        ranked_hits = rerank(query, hits, top_k=len(hits))
        seen_sources = set()
        group_count = 0
        for hit in ranked_hits:
            metadata = hit["metadata"]
            source = metadata.get("source", hit["id"])
            if source in seen_sources:
                continue
            seen_sources.add(source)

            result_id = metadata.get("record_id")
            if not isinstance(result_id, int) or isinstance(result_id, bool):
                result_id = source
                if is_case and isinstance(source, str) and source.startswith("incident_history::"):
                    source_id = source.removeprefix("incident_history::").split("::", 1)[0]
                    if source_id.isdigit():
                        result_id = int(source_id)

            results.append({
                "type": "case" if is_case else "kb",
                "id": result_id,
                "title": metadata.get("title") or hit["text"].splitlines()[0][:160],
                "text": hit["text"],
                "score": float(hit["rerank_score"]),
            })
            group_count += 1
            if group_count == limit:
                break

    return results


def format_context(hits: List[dict]) -> str:
    if not hits:
        return "No relevant context found in the knowledge base."

    context_parts = []
    seen = set()
    for hit in hits:
        text = clean_retrieval_text(hit["text"])
        if text and text not in seen:
            context_parts.append(text)
            seen.add(text)

    return "\n\n".join(context_parts) or "No relevant context found in the knowledge base."
