from typing import Any
import json
import re
import time
from RAG.retriever import retrieve_results as retrieve_rag_results

_QUERY_FIELDS = {
    "alert_title",
    "title",
    "alert",
    "detection_name",
    "rule_name",
    "alert_source",
    "source",
    "product",
    "vendor",
    "alert_description",
    "description",
    "message",
    "event_type",
    "severity",
    "alert_severity",
    "tactic",
    "technique",
    "host",
    "hostname",
    "endpoint",
    "agent",
    "device",
    "file",
    "file_name",
    "filename",
    "file_path",
    "path",
    "process",
    "process_name",
    "command_line",
    "user",
    "username",
}
_IOC_COLLECTION_FIELDS = {"alert_iocs", "iocs", "indicators"}
_NON_SEMANTIC_LABELS = {
    "agent", "host", "hostname", "endpoint", "device", "user", "username",
    "source", "alert_source", "product", "vendor", "severity", "alert_severity",
    "path", "file_path",
    "ioc", "ioc_type", "hash", "ip", "url", "email", "storyline", "site",
}
_GENERIC_ALERT_TERMS = {
    "alert", "detection", "detected", "event", "high", "incident", "level",
    "security", "suspicious", "threat",
}
# random file names only add noise to embeddings; their type is what describes the threat
_FILE_TYPES = {
    "exe": "executable", "scr": "executable", "msi": "installer package", "dll": "DLL library",
    "bat": "batch script", "cmd": "command script", "ps1": "PowerShell script", "vbs": "VBScript",
    "js": "JavaScript file", "jar": "Java archive", "lnk": "shortcut file", "iso": "disk image",
    "docm": "macro-enabled Office document", "xlsm": "macro-enabled Office spreadsheet",
    "doc": "Office document", "docx": "Office document", "xls": "Office spreadsheet",
    "xlsx": "Office spreadsheet", "pdf": "PDF document", "zip": "archive", "rar": "archive", "7z": "archive",
}
_FILE_NAME_PATTERN = re.compile(
    r"(?<![\w.\-])[\w][\w.\-]*\.(?P<ext>" + "|".join(_FILE_TYPES) + r")\b", re.IGNORECASE
)
_DOWNLOADS_PATH_PATTERN = re.compile(r"[\\/]downloads[\\/]", re.IGNORECASE)
_LOG_LABEL_PATTERN = re.compile(r"\b(?:file|path|process|image|sha1|sha256|sha512|ip|storyline|site)\s*:", re.IGNORECASE)
_LOG_FIELDS = {"generic_full_log", "windows_full_log", "full_log", "raw_log"}
_HASH_PATTERN = re.compile(r"\b(?:[a-f0-9]{128}|[a-f0-9]{64}|[a-f0-9]{40})\b", re.IGNORECASE)
_IP_PATTERN = re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)")
_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_LOG_VALUE_PATTERN = re.compile(
    r"(?:^|[.\s])(?P<label>file|path|process|image)\s*:\s*(?P<value>.*?)"
    r"(?=\s+(?:file|path|process|image|sha1|sha256|sha512|ip|storyline|site)\s*:|$)",
    re.IGNORECASE,
)


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
            if semantic and label.casefold() in _NON_SEMANTIC_LABELS:
                return
            text = " ".join(str(value).split()).rstrip(".,;")
            if not text:
                return
            if semantic and label.casefold() in {"alert_title", "title", "alert_description"}:
                signal_terms = {
                    token.casefold()
                    for token in re.findall(r"[A-Za-z][A-Za-z0-9.+_-]*", text)
                    if token.casefold() not in _GENERIC_ALERT_TERMS
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
                    if normalized_key in _QUERY_FIELDS:
                        add(str(key), value)
                    elif normalized_key in _IOC_COLLECTION_FIELDS and isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                add("ioc", item.get("ioc_value", item.get("value")))
                                add("ioc_type", item.get("ioc_type", item.get("type")))
                                add("ioc_description", item.get("ioc_description", item.get("description")))
                                add("ioc_tags", item.get("ioc_tags", item.get("tags")))
                            else:
                                add("ioc", item)
                    elif normalized_key in _LOG_FIELDS and isinstance(value, str):
                        if semantic:
                            add("log_message", _LOG_LABEL_PATTERN.split(value, maxsplit=1)[0])
                        for match in _LOG_VALUE_PATTERN.finditer(value):
                            add(match.group("label"), match.group("value"))
                        for pattern, label in (
                            (_HASH_PATTERN, "hash"),
                            (_IP_PATTERN, "ip"),
                            (_URL_PATTERN, "url"),
                            (_EMAIL_PATTERN, "email"),
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
            if _DOWNLOADS_PATH_PATTERN.search(json.dumps(incident, ensure_ascii=False, default=str)):
                add("origin", "downloaded by the user")
            parts = [
                _FILE_NAME_PATTERN.sub(lambda m: _FILE_TYPES[m.group("ext").lower()], part)
                for part in parts
            ]
        query = "\n".join(parts)
        return query[:1600] if query else json.dumps(incident, ensure_ascii=False, default=str)

