import logging
import math
import re
from collections import Counter
from typing import List, Literal, Optional
import config
from .embeddings import embed_query
from .reranker import rerank
from .text_cleaner import clean_retrieval_text, split_sentences
from .vector_store import get_collection

logger = logging.getLogger(__name__)

_RRF_K = 60
_TECHNIQUE_ID = re.compile(r"(?<![A-Za-z0-9])[Tt](\d{4})(?:[._](\d{3}))?(?!\d)")
_TOKEN = re.compile(r"[a-z0-9]+")
_LEXICAL_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "by", "detected", "detection",
    "for", "from", "high", "in", "is", "of", "on", "or", "the", "to",
    "with", "alert", "incident", "threat", "suspicious", "malicious",
    "source", "description", "title", "file", "origin", "log", "message",
    "security", "event", "user",
}


def _diversity_key(hit: dict) -> str:
    # the same MITRE technique can come from several sources/chunks: treat it as one result
    metadata = hit["metadata"]
    source = str(metadata.get("source") or "")
    match = _TECHNIQUE_ID.search(source) or _TECHNIQUE_ID.search(hit["text"][:300])
    if not match:
        return source
    return f"T{match.group(1)}" + (f".{match.group(2)}" if match.group(2) else "")


def _hit_key(hit: dict) -> str:
    metadata = hit["metadata"]
    source = metadata.get("source")
    chunk_index = metadata.get("chunk_index")
    if source is not None and chunk_index is not None:
        return f"{source}::{chunk_index}"
    return hit["text"]


def lexical_rank(query: str, hits: List[dict]) -> List[dict]:
    """Rank the vector candidates with BM25 over informative query terms."""
    query_terms = [
        token for token in _TOKEN.findall(query.casefold())
        if token not in _LEXICAL_STOP_WORDS and len(token) > 1
    ]
    if not query_terms or not hits:
        return list(hits)

    documents = [
        [
            token for token in _TOKEN.findall(hit["text"].casefold())
            if token not in _LEXICAL_STOP_WORDS and len(token) > 1
        ]
        for hit in hits
    ]
    document_frequency = Counter(
        token for token in set(term for term in query_terms)
        for document in documents if token in document
    )
    total_documents = len(documents)
    average_length = sum(map(len, documents)) / max(total_documents, 1)
    scores = []
    for original_rank, (hit, terms) in enumerate(zip(hits, documents)):
        frequencies = Counter(terms)
        score = 0.0
        for token in query_terms:
            frequency = frequencies[token]
            if not frequency:
                continue
            df = document_frequency[token]
            inverse_frequency = math.log(1 + (total_documents - df + 0.5) / (df + 0.5))
            denominator = frequency + 1.2 * (
                1 - 0.75 + 0.75 * len(terms) / max(average_length, 1)
            )
            score += inverse_frequency * frequency * 2.2 / denominator
        scores.append((score, original_rank, hit))
    scores.sort(key=lambda item: (-item[0], item[1]))
    for rank, (score, _, hit) in enumerate(scores, start=1):
        hit["lexical_score"] = score
        hit["lexical_rank"] = rank
    return [hit for _, _, hit in scores]


def select_hits(
    ranked_hits: List[dict],
    top_k: int,
    min_score: Optional[float] = None,
    margin: Optional[float] = None,
) -> List[dict]:

    min_score = config.RERANK_MIN_SCORE if min_score is None else min_score
    margin = config.RERANK_SCORE_MARGIN if margin is None else margin
    selected: List[dict] = []
    seen = set()
    for hit in ranked_hits:
        key = _diversity_key(hit)
        if key in seen:
            continue
        score = hit.get("rerank_score")
        if selected and score is not None:
            best = selected[0].get("rerank_score")
            if (min_score is not None and score < min_score) or (
                margin is not None and best is not None and score < best - margin
            ):
                break
        seen.add(key)
        selected.append(hit)
        if len(selected) >= top_k:
            break
    return selected


def fuse_rankings(
    vector_hits: List[dict],
    reranked_hits: List[dict],
    lexical_hits: Optional[List[dict]] = None,
    rerank_weight: Optional[float] = None,
    lexical_weight: Optional[float] = None,
) -> List[dict]:

    rerank_weight = config.RERANK_FUSION_WEIGHT if rerank_weight is None else rerank_weight
    lexical_weight = config.LEXICAL_FUSION_WEIGHT if lexical_weight is None else lexical_weight
    vector_rank = {_hit_key(hit): rank for rank, hit in enumerate(vector_hits, start=1)}
    lexical_rank_by_hit = {
        _hit_key(hit): rank for rank, hit in enumerate(lexical_hits or [], start=1)
    }
    for rank, hit in enumerate(reranked_hits, start=1):
        key = _hit_key(hit)
        position = vector_rank.get(key, len(vector_hits) + 1)
        lexical_position = lexical_rank_by_hit.get(key, len(vector_hits) + 1)
        hit["vector_rank"] = position
        hit["lexical_rank"] = lexical_position
        hit["fused_score"] = (
            1 / (_RRF_K + position)
            + rerank_weight / (_RRF_K + rank)
            + lexical_weight / (_RRF_K + lexical_position)
        )
    return sorted(reranked_hits, key=lambda hit: hit["fused_score"], reverse=True)


def merge_chunks(current: str, following: str, title: Optional[str] = None) -> str:

    if title and following.startswith(f"{title}: "):
        following = following[len(title) + 2:]
    current_sentences = split_sentences(current)
    following_sentences = split_sentences(following)
    for shared in range(min(len(current_sentences), len(following_sentences)), 0, -1):
        if current_sentences[-shared:] == following_sentences[:shared]:
            following_sentences = following_sentences[shared:]
            break
    return " ".join([current, *following_sentences]).strip()


def expand_hits(collection, hits: List[dict], count: int) -> None:

    for hit in hits[:count]:
        metadata = hit["metadata"]
        index = metadata.get("chunk_index")
        source = metadata.get("source")
        if not isinstance(index, int) or isinstance(index, bool) or not source:
            continue
        try:
            found = collection.get(ids=[f"{source}::{index + 1}"], include=["documents"])
            documents = found.get("documents") or []
        except Exception:
            logger.warning("Could not load the chunk following %s::%s", source, index, exc_info=True)
            continue
        if documents:
            hit["text"] = merge_chunks(hit["text"], clean_retrieval_text(documents[0]), metadata.get("title"))


def retrieve(
    query: str,
    customer_id: int,
    top_k: int = config.TOP_K,
    result_kind: Optional[Literal["case", "kb"]] = None,
) -> List[dict]:
    if isinstance(customer_id, bool) or not isinstance(customer_id, int) or customer_id <= 0:
        raise ValueError("customer_id must be a positive integer for tenant-scoped retrieval")

    # get ChromaDB collection
    collection = get_collection()

    if collection.count() == 0:
        return []

    candidate_k = min(max(top_k, config.RERANK_CANDIDATES), collection.count())

    # generate query embedding
    query_embedding = embed_query(query)

    # ChromaDB vector search
    if result_kind == "case":
        where = {
            "$and": [
                {"category": "incident_history"},
                {"customer": customer_id},
            ]
        }
    elif result_kind == "kb":
        where = {
            "$and": [
                {"scope": "global"},
                {"category": {"$ne": "incident_history"}},
            ]
        }
    else:
        where = {"$or": [{"scope": "global"}, {"customer": customer_id}]}

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=candidate_k,
        where=where,
    )

    # build hits
    hits = []
    for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
        cleaned_doc = clean_retrieval_text(doc)
        if cleaned_doc:
            hits.append({"text": cleaned_doc, "metadata": meta, "distance": dist})

    # reranking
    reranked_hits = rerank(query, hits, top_k=len(hits))
    lexical_hits = lexical_rank(query, hits)
    fused_hits = fuse_rankings(hits, reranked_hits, lexical_hits)
    ranked_hits = select_hits(fused_hits, top_k)
    expand_hits(collection, ranked_hits, config.CONTEXT_EXPAND_TOP)

    return ranked_hits


def retrieve_results(
    query: str,
    customer_id: int,
    k_cases: int,
    k_kb: int,
) -> List[dict]:
    if isinstance(customer_id, bool) or not isinstance(customer_id, int) or customer_id <= 0:
        raise ValueError("customer_id must be a positive integer for tenant-scoped retrieval")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    for name, limit in (("k_cases", k_cases), ("k_kb", k_kb)):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 0 <= limit <= 100:
            raise ValueError(f"{name} must be an integer between 0 and 100")

    results = []
    for result_kind, limit in (("case", k_cases), ("kb", k_kb)):
        if limit == 0:
            continue
        hits = retrieve(
            query,
            customer_id=customer_id,
            top_k=limit,
            result_kind=result_kind,
        )
        for hit in hits:
            metadata = hit["metadata"]
            record_id = metadata.get("record_id")
            if result_kind == "case":
                if isinstance(record_id, bool) or not isinstance(record_id, int):
                    raise ValueError("Retrieved case is missing a numeric record_id")
                result_id = record_id
            else:
                result_id = record_id or metadata.get("source", "")
            results.append(
                {
                    "type": result_kind,
                    "id": result_id,
                    "title": metadata.get("title") or metadata.get("source", ""),
                    "text": hit["text"],
                    "score": float(hit["fused_score"]),
                }
            )

    return sorted(results, key=lambda result: result["score"], reverse=True)
