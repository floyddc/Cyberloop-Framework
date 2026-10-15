import os

RAG_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(RAG_DIR)
_knowledge_candidates = [
    os.environ.get("KNOWLEDGE_DIR", ""),
    os.path.join(RAG_DIR, "knowledge"),  
    os.path.join(PROJECT_ROOT, "knowledge"),  
]
KNOWLEDGE_DIR = next(
    (p for p in _knowledge_candidates if p and os.path.isdir(p)),
    _knowledge_candidates[-1],
)
BASE_DIR = os.path.join(KNOWLEDGE_DIR, "base")
POLICIES_DIR = os.path.join(KNOWLEDGE_DIR, "policies")
ACTIONS_CATALOG_DIR = os.path.join(KNOWLEDGE_DIR, "actions_catalog")
PROCESSED_DIR = os.path.join(KNOWLEDGE_DIR, "processed_data")
INDICES_DIR = os.path.join(KNOWLEDGE_DIR, "indices")
CACHE_DIR = os.environ.get(
    "CACHE_DIR",
    os.path.join(os.path.expanduser("~"), ".cache", "huggingface"),
)
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# RERANKER & EMBEDDER (CPU MODELS) ----------------------------------------------------------------------------------------------------------------------------------------------------------     
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
TOP_K = 5
RERANKER_MODEL = os.environ.get("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L2-v2")
RERANK_CANDIDATES = int(os.environ.get("RERANK_CANDIDATES", "10"))
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")

# DB ----------------------------------------------------------------------------------------------------------------------------------------------------------     
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "cyberresponse")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "cyberresponse")
POSTGRES_KNOWLEDGE_DB = os.environ.get("POSTGRES_KNOWLEDGE_DB", "knowledge")
COLLECTION_NAME = "cyber_response_kb"
