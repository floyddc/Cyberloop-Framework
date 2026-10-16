from typing import Any, Dict, Optional
import config
import json
import logging as logging
import logging as _logging
import argparse
from RAG.context_builder import build_context
from RAG.retriever import retrieve_results as retrieve_rag_results

logger = logging.getLogger(__name__)

class RetrieveAgent:

    def __init__(self, top_k: int = config.TOP_K):
        self.top_k = top_k
        self.logger = logger

    def retrieve_results(
        self,
        query: str,
        customer_id: int,
        k_cases: int,
        k_kb: int,
    ) -> list[dict]:
        return retrieve_rag_results(
            query,
            customer_id=customer_id,
            k_cases=k_cases,
            k_kb=k_kb,
        )

    def _incident_to_query(self, incident: Any) -> str:

        if isinstance(incident, str): return incident

        if not isinstance(incident, dict): return str(incident)

        # Convert recursively a JSON into lines
        def flatten(data: Any, prefix: str = "") -> list[str]:
            
            parts = []

            if isinstance(data, dict):
                for key, value in data.items():

                    field_name = f"{prefix}.{key}" if prefix else str(key)

                    if value is None or value == "":
                        continue

                    if isinstance(value, dict): parts.extend(flatten(value, field_name))

                    elif isinstance(value, list):
                        for index, item in enumerate(value):
                            item_path = f"{field_name}.{index}"
                            if isinstance(item, (dict, list)):
                                parts.extend(flatten(item, item_path))
                            elif item is not None and item != "":
                                parts.append(f"{item_path}: {item}")

                    else:
                        parts.append(f"{field_name}: {value}")

            elif isinstance(data, list):
                for index, item in enumerate(data):
                    item_path = f"{prefix}.{index}" if prefix else str(index)
                    if isinstance(item, (dict, list)):
                        parts.extend(flatten(item, item_path))
                    elif item is not None and item != "":
                        parts.append(f"{item_path}: {item}")

            return parts

        raw_payload = incident.get("raw_payload")

        if isinstance(raw_payload, dict):

            parts = []
            source = incident.get("source")

            if source: parts.append(f"source: {source}")

            parts.extend(flatten(raw_payload))

            if parts: return "\n".join(parts)

            return json.dumps(raw_payload, ensure_ascii=False, default=str)

        # Fallback
        parts = flatten(incident)

        if parts: return "\n".join(parts)

        return json.dumps(incident, ensure_ascii=False, default=str)

    
    def retrieve(self, incident_or_query: Any, incident_id: int = None, customer_id: Optional[int] = None) -> Dict[str, str]:
        q = self._incident_to_query(incident_or_query)
        if isinstance(incident_or_query, dict):
            incident_customer_id = incident_or_query.get("customer_id")
            if customer_id is not None and customer_id != incident_customer_id:
                raise ValueError("customer_id does not match the incident tenant")
            customer_id = incident_customer_id

        context = ""
        
        try:
            if isinstance(customer_id, bool) or not isinstance(customer_id, int) or customer_id <= 0:
                raise ValueError("customer_id must be a positive integer for tenant-scoped retrieval")
            
            context = build_context(q, customer_id=customer_id, top_k=self.top_k)
            return {"query": q, "context": context}

        except Exception as exc:
            self.logger.exception("Retrieve failed")
            return {"query": q, "error": str(exc)}


if __name__ == "__main__":

    _logging.basicConfig(level=_logging.INFO)
    for lib in ("httpx", "sentence_transformers", "transformers", "urllib3", "chromadb"):
        _logging.getLogger(lib).setLevel(_logging.WARNING)

    agent = RetrieveAgent()
    parser = argparse.ArgumentParser()
    parser.add_argument("--customer-id", required=True, type=int)
    parser.add_argument("query", nargs="*")
    args = parser.parse_args()
    q = " ".join(args.query) or input("Incident or query: ")
    out = agent.retrieve(q, customer_id=args.customer_id)
    print(json.dumps(out, indent=2, ensure_ascii=False))