from typing import Any
import json
import re
import config
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
            self._incident_to_query(incident_or_query, semantic=True),
            customer_id=customer_id,
            k_cases=k_cases,
            k_kb=k_kb,
        )

    def _incident_to_query(self, incident: Any, semantic: bool = False) -> str:

        if isinstance(incident, str): return incident
        if not isinstance(incident, dict): return str(incident)
        parts = []
        seen = set()

        def add(label: str, value: Any, limit: int = 240) -> None:
            if isinstance(value, (dict, list)) or value is None:
                return
            if semantic and label.casefold() in config._NON_SEMANTIC_LABELS:
                return
            text = " ".join(str(value).split()).rstrip(".,;")
            if not text:
                return
            if semantic and label.casefold() in {"alert_title", "title", "alert_description"}:
                signal_terms = {
                    token.casefold()
                    for token in re.findall(r"[A-Za-z][A-Za-z0-9.+_-]*", text)
                    if token.casefold() not in config._GENERIC_ALERT_TERMS
                }
                if len(signal_terms) < 2:
                    return
            text = text[:limit]
            entry = f"{label.casefold()}: {text}"
            if entry.casefold() not in seen:
                parts.append(entry)
                seen.add(entry.casefold())

        def visit(data: Any) -> None:
            if isinstance(data, dict):
                for key, value in data.items():
                    normalized_key = str(key).casefold()
                    if normalized_key in config._QUERY_FIELDS:
                        add(str(key), value)
                    elif normalized_key in config._IOC_COLLECTION_FIELDS and isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                add("ioc", item.get("ioc_value", item.get("value")))
                                add("ioc_type", item.get("ioc_type", item.get("type")))
                                add("ioc_description", item.get("ioc_description", item.get("description")))
                                add("ioc_tags", item.get("ioc_tags", item.get("tags")))
                            else:
                                add("ioc", item)
                    elif normalized_key in config._LOG_FIELDS and isinstance(value, str):
                        if semantic:
                            add("log_message", config._LOG_LABEL_PATTERN.split(value, maxsplit=1)[0])
                        for match in config._LOG_VALUE_PATTERN.finditer(value):
                            add(match.group("label"), match.group("value"))
                        for pattern, label in (
                            (config._HASH_PATTERN, "hash"),
                            (config._IP_PATTERN, "ip"),
                            (config._URL_PATTERN, "url"),
                            (config._EMAIL_PATTERN, "email"),
                        ):
                            for match in pattern.findall(value):
                                add(label, match)
                    elif isinstance(value, (dict, list)):
                        visit(value)
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, (dict, list)):
                        visit(item)

        visit(incident)
        if semantic:
            if config._DOWNLOADS_PATH_PATTERN.search(json.dumps(incident, ensure_ascii=False, default=str)):
                add("origin", "downloaded by the user")
            parts = [
                config._FILE_NAME_PATTERN.sub(lambda m: config._FILE_TYPES[m.group("ext").lower()], part)
                for part in parts
            ]
        query = "\n".join(parts)
        return query[:1600] if query else json.dumps(incident, ensure_ascii=False, default=str)