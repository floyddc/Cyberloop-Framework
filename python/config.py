import os
import re

# DB ----------------------------------------------------------------------------------------------------------------------------------------------------------     
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "cyberresponse")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "cyberresponse")
POSTGRES_KNOWLEDGE_DB = os.environ.get("POSTGRES_KNOWLEDGE_DB", "knowledge")
COLLECTION_NAME = "cyber_response_kb"

# RERANKER & EMBEDDER ----------------------------------------------------------------------------------------------------------------------------------------------------------     
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-base")    # da cambiare se non gira bene in locale (alternativa leggera: intfloat/multilingual-e5-small)
RERANKER_MODEL = os.environ.get("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")            # da cambiare se non gira bene in locale (alternativa leggera: cross-encoder/ms-marco-MiniLM-L2-v2)
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
TOP_K = 5
RERANK_CANDIDATES = int(os.environ.get("RERANK_CANDIDATES", "10"))
RERANK_MIN_SCORE = None         
RERANK_SCORE_MARGIN = None      
RERANK_FUSION_WEIGHT = 1.0      
LEXICAL_FUSION_WEIGHT = 1.5     
CONTEXT_EXPAND_TOP = 1  

# DIRECTORIES ----------------------------------------------------------------------------------------------------------------------------------------------------------     
RAG_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(RAG_DIR)
_knowledge_candidates = [
    os.environ.get("KNOWLEDGE_DIR", ""),
    os.path.join(RAG_DIR, "knowledge"),  
    os.path.join(PROJECT_ROOT, "knowledge"),  
]
KNOWLEDGE_DIR = next((p for p in _knowledge_candidates if p and os.path.isdir(p)),  _knowledge_candidates[-1],)
BASE_DIR = os.path.join(KNOWLEDGE_DIR, "base")
POLICIES_DIR = os.path.join(KNOWLEDGE_DIR, "policies")
ACTIONS_CATALOG_DIR = os.path.join(KNOWLEDGE_DIR, "actions_catalog")
PROCESSED_DIR = os.path.join(KNOWLEDGE_DIR, "processed_data")
INDICES_DIR = os.path.join(KNOWLEDGE_DIR, "indices")
CACHE_DIR = os.environ.get("CACHE_DIR", os.path.join(os.path.expanduser("~"), ".cache", "huggingface"))


# RETRIEVE PARAMETERS ----------------------------------------------------------------------------------------------------------------------------------------------------------     
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
_FILE_TYPES = {
    "exe": "executable", "scr": "executable", "msi": "installer package", "dll": "DLL library",
    "bat": "batch script", "cmd": "command script", "ps1": "PowerShell script", "vbs": "VBScript",
    "js": "JavaScript file", "jar": "Java archive", "lnk": "shortcut file", "iso": "disk image",
    "docm": "macro-enabled Office document", "xlsm": "macro-enabled Office spreadsheet",
    "doc": "Office document", "docx": "Office document", "xls": "Office spreadsheet",
    "xlsx": "Office spreadsheet", "pdf": "PDF document", "zip": "archive", "rar": "archive", "7z": "archive",
}
_FILE_NAME_PATTERN = re.compile(r"(?<![\w.\-])[\w][\w.\-]*\.(?P<ext>" + "|".join(_FILE_TYPES) + r")\b", re.IGNORECASE)
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
_TITLE_PATTERN = re.compile(r"^#\s*(?P<title>.+?)(?:\s+##\s|\s*\?(?:\s|$)|$)")
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