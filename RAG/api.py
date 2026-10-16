import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import Annotated, Literal, Optional
from fastapi import FastAPI, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator
from python.retrieve_agent import RetrieveAgent
from .embeddings import embed_query
from .reranker import warmup as warmup_reranker
from .ingestion import SourceDocument, build_chunks
from .knowledge_store import IncidentHistoryStore
from .vector_store import replace_source_records

logging.basicConfig(stream=sys.stdout, level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("rag-service")

CustomerId = Annotated[StrictInt, Field(gt=0)]
CaseId = Annotated[StrictInt, Field(gt=0)]


class RetrieveRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    customer: CustomerId
    query: str = Field(min_length=1, max_length=1600)
    k_cases: int = Field(default=5, ge=0, le=100)
    k_kb: int = Field(default=5, ge=0, le=100)


class CaseInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    id: Optional[CaseId] = None
    customer: CustomerId
    title: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1, max_length=100_000)


class CasesIndexRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cases: list[CaseInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_case_ids(self) -> "CasesIndexRequest":
        ids = [case.id for case in self.cases if case.id is not None]
        if len(ids) != len(set(ids)):
            raise ValueError("case ids must be unique within a batch")
        return self


class RetrieveResult(BaseModel):
    type: Literal["case", "kb"]
    id: int | str
    title: str
    text: str
    score: float


def _warm_models() -> None:
    embed_query("warm-up query")
    warmup_reranker()

_models_ready = False

@asynccontextmanager
async def lifespan(_: FastAPI):
    global _models_ready
    _models_ready = False
    _warm_models()
    _models_ready = True
    logger.info("Embedding and reranker models are ready")
    try:
        yield
    finally:
        _models_ready = False

app = FastAPI(title="Cyberloop RAG service", lifespan=lifespan)


def _require_ready() -> None:
    if not _models_ready:
        raise HTTPException(status_code=503, detail="Models are not ready")


@app.get("/health")
def health() -> dict:
    if not _models_ready:
        raise HTTPException(status_code=503, detail="Models are not ready")
    return {"status": "ok"}


@app.post("/retrieve", response_model=list[RetrieveResult])
def retrieve_results(request: RetrieveRequest) -> list[dict]:
    _require_ready()
    return RetrieveAgent().retrieve_results(
        request.query,
        customer_id=request.customer,
        k_cases=request.k_cases,
        k_kb=request.k_kb,
    )


@app.post("/index/cases")
def index_cases(request: CasesIndexRequest) -> dict:
    _require_ready()
    store = IncidentHistoryStore()
    case_ids = []
    for case in request.cases:
        case_id = store.upsert_case(case.id, case.customer, case.title, case.text)
        source = f"incident_history::{case_id}"
        document = SourceDocument(
            path=source,
            category="incident_history",
            content=f"summary: {case.title}\ndescription: {case.text}",
            metadata={
                "customer": case.customer,
                "scope": "customer",
                "title": case.title,
                "record_id": case_id,
            },
        )
        replace_source_records(source, build_chunks([document]))
        case_ids.append(case_id)

    logger.info("Indexed %s historical case(s): %s", len(case_ids), case_ids)
    return {"indexed": len(case_ids), "ids": case_ids}


@app.delete("/index/cases/{case_id}")
def delete_case(case_id: Annotated[int, Path(gt=0)]) -> dict:
    _require_ready()
    if not IncidentHistoryStore().delete_case(case_id):
        raise HTTPException(status_code=404, detail="Case not found")

    replace_source_records(f"incident_history::{case_id}", [])
    logger.info("Deleted historical case %s", case_id)
    return {"deleted": True, "id": case_id}
