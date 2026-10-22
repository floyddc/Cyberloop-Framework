from typing import Any
import json
from RAG.retriever import retrieve_results as retrieve_rag_results


class RetrieveAgent:

    def retrieve(
        self,
        incident_or_query: Any,
        customer_id: int,
        k_cases: int,
        k_kb: int,
    ) -> list[dict]:
        return retrieve_rag_results(
            self._incident_to_query(incident_or_query),
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

