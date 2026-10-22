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

# RERANKER & EMBEDDER ----------------------------------------------------------------------------------------------------------------------------------------------------------     
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
TOP_K = 5
RERANKER_MODEL = os.environ.get("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
RERANK_CANDIDATES = int(os.environ.get("RERANK_CANDIDATES", "10"))
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "intfloat/multilingual-e5-base")
RERANK_MIN_SCORE = None         
RERANK_SCORE_MARGIN = None      
RERANK_FUSION_WEIGHT = 1.0      
LEXICAL_FUSION_WEIGHT = 1.5     
CONTEXT_EXPAND_TOP = 1  

# DB ----------------------------------------------------------------------------------------------------------------------------------------------------------     
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "cyberresponse")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "cyberresponse")
POSTGRES_KNOWLEDGE_DB = os.environ.get("POSTGRES_KNOWLEDGE_DB", "knowledge")
COLLECTION_NAME = "cyber_response_kb"
