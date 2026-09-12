from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.api.state import state
from backend.ai.llm_reasoner import GroundedReasoner

router = APIRouter(prefix="/api/investigate", tags=["Investigation"])

class QueryRequest(BaseModel):
    query: str

@router.post("/query")
def investigate_query(req: QueryRequest):
    if not state.current_batch or not state.embedding_index:
        raise HTTPException(
            status_code=400,
            detail="No dataset is loaded. Ingest a dataset before running investigation queries."
        )

    reasoner = GroundedReasoner()
    result = reasoner.investigate_query(
        query=req.query,
        logs=state.current_batch.logs,
        embedding_index=state.embedding_index
    )
    return result
