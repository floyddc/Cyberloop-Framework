import json
import logging
from typing import Any, Dict, Optional, Protocol
import config
import time
from RAG.context_builder import retrieve_context
from ollama import Client
from .logging_agent import logging_agent


logger = logging.getLogger(__name__)


class ChatClient(Protocol):
    def chat(self, **kwargs: Any) -> Any: ...


class TriageAgent:

    def __init__(self, model: str = config.TRIAGE_MODEL, host: str = config.OLLAMA_HOST, client: Optional[ChatClient] = None):
        self.model = model
        self.client = Client(host=host)

    def _heuristic_severity(self, raw_payload: Dict[str, Any]) -> str:
        text = json.dumps(raw_payload).lower()
        if any(k in text for k in ("ransomware", "critical", "root_shell", "lateral_movement")):
            return "critical"
        if any(k in text for k in ("privilege_escalation", "exfiltration", "c2", "malware")):
            return "high"
        if any(k in text for k in ("suspicious", "anomaly", "failed_login")):
            return "medium"
        return "low"

    def _llm_triage(self, raw_payload: Dict[str, Any], context: str = "") -> Optional[Dict[str, Any]]:
        try:
            alert = {
                key: value
                for key, value in raw_payload.items()
                if key not in {"customer", "_source", "external_id"}
            }
            messages = [
                {
                    "role": "system",
                    "content": config.TRIAGE_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": (
                        "SECURITY ALERT:\n"
                        f"{json.dumps(alert, ensure_ascii=False, default=str)}\n\n"
                        "RETRIEVED SECURITY CONTEXT:\n"
                        f"{context or '(no relevant context retrieved)'}"
                    ),
                },
            ]
            response = self.client.chat(model=self.model, messages=messages, format="json", keep_alive=-1)
            content = response["message"]["content"]
            data = json.loads(content)
            if data.get("severity") not in config.VALID_SEVERITIES:
                data["severity"] = self._heuristic_severity(raw_payload)
            return data
        except Exception:
            logger.exception("LLM triage failed, falling back to heuristic classification")
            return None

    def triage(self, alert: Dict[str, Any], context: Optional[str] = None) -> Dict[str, Any]:

        start = time.perf_counter()
        result = self._llm_triage(raw_payload, source, context)
        llm_total_ms = (time.perf_counter() - start) * 1000
        fallback_used = result is None

        if not isinstance(alert, dict):
            raise ValueError("alert must be a JSON object")
        if context is None:
            context = retrieve_context(alert)
        elif not isinstance(context, str):
            raise ValueError("context must be a string")
        source = alert.get("_source", "security")
        raw_payload = {
            key: value
            for key, value in alert.items()
            if key not in {"customer", "_source", "external_id"}
        }
        result = self._llm_triage(raw_payload, context)

        if result is None:
            result = {
                "summary": f"{source} alert",
                "description": json.dumps(raw_payload, ensure_ascii=False),
                "category": "unknown",
                "severity": self._heuristic_severity(raw_payload)
            }

        logging_agent.record("triage_agent", "triage", status="success", duration_ms=llm_total_ms, incident_id=incident_id,
            details={
                "model": self.model,
                "fallback_used": fallback_used,
                "context_length": len(context or ""),
                "raw_payload_length": len(json.dumps(raw_payload, ensure_ascii=False, default=str)),
                "severity": result.get("severity"),
                "category": result.get("category")
            }
        )
        return result
