import config
from .retriever import retrieve, format_context

class ContextBuilder:

    def __init__(self, retriever_func=retrieve, top_k: int = config.TOP_K):
        self.retriever_func = retriever_func
        self.top_k = top_k

    def build(self, query: str, customer_id: int) -> str:
        hits = self.retriever_func(
            query,
            customer_id=customer_id,
            top_k=self.top_k,
        )
        return format_context(hits)

def build_context(
    query: str,
    customer_id: int,
    top_k: int = config.TOP_K,
) -> str:
    return ContextBuilder(top_k=top_k).build(query, customer_id)
