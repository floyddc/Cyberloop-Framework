import config
from .retriever import retrieve, format_context
import json
from typing import Any, Dict, Optional

class ContextBuilder:

    def __init__(self, retriever_func=retrieve, top_k: int = config.TOP_K, retrieval_metrics: Optional[Dict[str, Any]] = None):
        self.retriever_func = retriever_func
        self.top_k = top_k
        self.retrieval_metrics = retrieval_metrics

    def build(self, alert: Dict[str, Any]) -> str:
        customer, query = alert_to_query(alert)
        hits = self.retriever_func(
            query,
            customer=customer,
            top_k=self.top_k,
            metrics=self.retrieval_metrics,
        )
        return format_context(hits)


def alert_to_query(alert: Dict[str, Any]) -> tuple[str, str]:
    if not isinstance(alert, dict):
        raise ValueError("alert must be a JSON object")

    customer = alert.get("customer")
    if not isinstance(customer, str) or not customer.strip():
        raise ValueError("alert must contain a non-empty 'customer' field")

    query_fields = {
        key: value
        for key, value in alert.items()
        if key not in {"customer", "_source", "external_id"}
    }
    query = json.dumps(query_fields, ensure_ascii=False, sort_keys=True, default=str).strip()
    if not query_fields:
        raise ValueError("alert must contain fields other than 'customer'")

    return customer.strip(), query


def build_context(
    alert: Dict[str, Any],
    top_k: int = config.TOP_K,
    retrieval_metrics: Optional[Dict[str, Any]] = None,
) -> str:
    return ContextBuilder(top_k=top_k, retrieval_metrics=retrieval_metrics).build(alert)


def retrieve_context(
    alert: Dict[str, Any],
    top_k: int = config.TOP_K,
    retrieval_metrics: Optional[Dict[str, Any]] = None,
) -> str:
    return build_context(alert, top_k=top_k, retrieval_metrics=retrieval_metrics)
