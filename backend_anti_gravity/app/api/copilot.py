"""
api/copilot.py — Copilot endpoint: /api/v1/copilot/query (JSON) and /api/v1/copilot/stream (SSE).
"""
from __future__ import annotations
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend_anti_gravity.app.api.deps import get_current_user, get_db
from backend_anti_gravity.app.models.auth import User
from backend_anti_gravity.app.schemas.copilot import CopilotRequest, CopilotResponse
from backend_anti_gravity.app.services.copilot_agent import run_copilot, stream_copilot

router = APIRouter(prefix="/copilot", tags=["AI Copilot"])


@router.post("/query", response_model=CopilotResponse)
async def copilot_query(
    payload: CopilotRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Non-streaming copilot endpoint.
    
    Pipeline:
      1. Classify intent from natural language query.
      2. Route to pre-built database tool handler (no LLM math).
      3. Extract structured data via ORM.
      4. Pass data to LLM for narrative explanation only.
      5. Return structured JSON response with full audit trail.
    
    Pre-built handlers:
      - "reorder" / "what should I order" → stock vs reorder_point vs lead_time query
      - "why are returns increasing" → return table × shipment damage × review sentiment
      - "stockout" → products at zero or below safety threshold
      - "revenue" → sales aggregate summary
      - "delay" → shipment delay statistics
    """
    result = await run_copilot(
        query=payload.query,
        db=db,
        context=payload.context,
    )
    return CopilotResponse(**result)


@router.post("/stream")
async def copilot_stream(
    payload: CopilotRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Streaming Server-Sent Events (SSE) copilot endpoint.
    
    Returns a text/event-stream response with sequential JSON chunks:
      - {"type": "intent",     "content": "reorder_recommendation"}
      - {"type": "tool_call",  "content": "Executing: reorder_recommendation"}
      - {"type": "data",       "content": "{...structured db results...}"}
      - {"type": "narrative",  "content": "chunk of LLM explanation..."}  (repeated)
      - {"type": "done",       "content": "", "confidence": 0.90}
    
    Frontend should parse each 'data:' line as JSON and render progressively.
    """
    return StreamingResponse(
        stream_copilot(query=payload.query, db=db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
