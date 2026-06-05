"""
api/copilot.py — Copilot endpoints:
- POST /api/v1/copilot/query      -> one-shot JSON response
- GET  /api/v1/copilot/stream     -> SSE streaming response
- WS   /api/v1/copilot/ws         -> WebSocket chatbot response
"""

from __future__ import annotations

import inspect
import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from .deps import get_current_user, get_db
from ..models.auth import User
from ..schemas.copilot import CopilotRequest, CopilotResponse
from ..services.copilot_agent import run_copilot, stream_copilot
from ..services.copilot_session_history import append_copilot_turn, HISTORY_PATH
from ..services.copilot_query_cache import COMMON_QUERY_MEMORY
from ..services.copilot_insights import (
    build_dashboard_insights,
    build_forecast_commentary,
    build_product_recommendations,
)

router = APIRouter(prefix="/copilot", tags=["AI Copilot"])


class InsightOut(BaseModel):
    insights: list[str]


class CopilotExampleOut(BaseModel):
    query: str
    category: str
    description: str
    tables: list[str]


# ─────────────────────────────────────────────────────────────
# DEBUG ROUTE
# ─────────────────────────────────────────────────────────────
@router.get("/debug")
async def copilot_debug():
    """
    Temporary debug endpoint.
    Use this to verify which copilot_agent.py file is actually running.
    """
    return {
        "message": "Copilot API debug route is live",
        "engine_expected": "LLM_SQL_AGENT_V2",
        "run_copilot_module": run_copilot.__module__,
        "run_copilot_file": inspect.getfile(run_copilot),
        "stream_copilot_module": stream_copilot.__module__,
        "stream_copilot_file": inspect.getfile(stream_copilot),
    }


@router.get("/examples", response_model=list[CopilotExampleOut])
async def copilot_examples(_: User = Depends(get_current_user)):
    """Common live-data questions shown as Copilot starter examples."""
    return [CopilotExampleOut(**item) for item in COMMON_QUERY_MEMORY]


@router.get("/history")
async def copilot_history(_: User = Depends(get_current_user)):
    if not HISTORY_PATH.exists():
        return {"turns": []}
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"turns": []}


# ─────────────────────────────────────────────────────────────
# NON-STREAMING COPILOT
# ─────────────────────────────────────────────────────────────
@router.post("/query", response_model=CopilotResponse)
async def copilot_query(
    payload: CopilotRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Non-streaming copilot endpoint.

    Frontend sends:
    {
      "query": "how much stock do we have of Samsung Galaxy S23 Ultra",
      "context": {}
    }

    Backend returns one complete JSON response.
    """
    result = await run_copilot(
        query=payload.query,
        db=db,
        context=payload.context,
    )

    # Put debug marker inside data_context because response_model may remove extra top-level keys.
    result.setdefault("data_context", {})
    result["data_context"]["api_debug"] = {
        "api_file": "api/copilot.py",
        "engine_expected": "LLM_SQL_AGENT_V2",
        "run_copilot_module": run_copilot.__module__,
        "run_copilot_file": inspect.getfile(run_copilot),
    }

    return CopilotResponse(**result)


# ─────────────────────────────────────────────────────────────
# WEBSOCKET CHATBOT COPILOT
# ─────────────────────────────────────────────────────────────
@router.websocket("/ws")
async def copilot_websocket(
    websocket: WebSocket,
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket endpoint for chatbot UI.

    Frontend connects:
    ws://localhost:8000/api/v1/copilot/ws

    Frontend sends:
    {
      "query": "how much stock do we have of Samsung Galaxy S23 Ultra",
      "context": {}
    }

    Backend streams:
    {
      "type": "intent" | "tool_call" | "data" | "narrative" | "done" | "error",
      "content": "..."
    }

    This version safely handles browser refresh, page change,
    reconnect, and frontend WebSocket disconnects.
    """
    await websocket.accept()

    async def safe_send(event: dict) -> bool:
        """
        Send JSON to websocket safely.

        Returns:
            True  -> message sent successfully
            False -> client disconnected / socket closed
        """
        try:
            await websocket.send_json(event)
            return True
        except WebSocketDisconnect:
            return False
        except RuntimeError:
            return False
        except Exception:
            return False

    if not await safe_send(
        {
            "type": "connection",
            "content": "Copilot WebSocket connected",
        }
    ):
        return

    if not await safe_send(
        {
            "type": "version",
            "content": "LLM_SQL_AGENT_V2_FROM_WEBSOCKET",
        }
    ):
        return

    try:
        while True:
            try:
                payload = await websocket.receive_json()

            except WebSocketDisconnect:
                print("Copilot WebSocket disconnected")
                return

            except json.JSONDecodeError:
                if not await safe_send(
                    {
                        "type": "error",
                        "content": 'Invalid JSON payload. Send {"query": "your question"}.',
                    }
                ):
                    return
                continue

            except RuntimeError:
                print("Copilot WebSocket connection closed")
                return

            except Exception:
                if not await safe_send(
                    {
                        "type": "error",
                        "content": 'Invalid JSON payload. Send {"query": "your question"}.',
                    }
                ):
                    return
                continue

            if not isinstance(payload, dict):
                if not await safe_send(
                    {
                        "type": "error",
                        "content": 'Invalid payload. Send {"query": "your question"}.',
                    }
                ):
                    return
                continue

            query = str(payload.get("query", "")).strip()

            if not query:
                if not await safe_send(
                    {
                        "type": "error",
                        "content": "Query is required.",
                    }
                ):
                    return
                continue

            if not await safe_send(
                {
                    "type": "received",
                    "content": query,
                }
            ):
                return

            context = payload.get("context")
            if not isinstance(context, dict):
                context = {}

            answer_parts: list[str] = []

            try:
                async for sse_chunk in stream_copilot(query=query, db=db, context=context):
                    # stream_copilot yields strings like:
                    # data: {"type":"narrative","content":"..."}\n\n

                    for line in sse_chunk.splitlines():
                        line = line.strip()

                        if not line.startswith("data:"):
                            continue

                        raw_json = line.replace("data:", "", 1).strip()

                        if not raw_json:
                            continue

                        try:
                            event = json.loads(raw_json)
                        except json.JSONDecodeError:
                            event = {
                                "type": "raw",
                                "content": raw_json,
                            }

                        if not isinstance(event, dict):
                            event = {
                                "type": "raw",
                                "content": str(event),
                            }

                        if not await safe_send(event):
                            return

                        if event.get("type") == "narrative":
                            answer_parts.append(str(event.get("content") or ""))

                        elif event.get("type") == "done":
                            try:
                                append_copilot_turn(query, "".join(answer_parts), context)
                            except Exception:
                                pass

            except WebSocketDisconnect:
                print("Copilot WebSocket disconnected during stream")
                return

            except RuntimeError:
                print("Copilot WebSocket closed during stream")
                return

            except Exception as exc:
                if not await safe_send(
                    {
                        "type": "error",
                        "content": str(exc),
                    }
                ):
                    return

    except WebSocketDisconnect:
        print("Copilot WebSocket disconnected")

    except Exception as exc:
        await safe_send(
            {
                "type": "error",
                "content": str(exc),
            }
        )


# ─────────────────────────────────────────────────────────────
# SSE STREAMING COPILOT
# ─────────────────────────────────────────────────────────────
@router.get("/stream")
async def copilot_stream(
    query: str,
    db: AsyncSession = Depends(get_db),
):
    """
    SSE streaming endpoint.

    Test in browser:
    http://127.0.0.1:8000/api/v1/copilot/stream?query=Samsung%20Galaxy%20S23%20Ultra
    """

    async def debug_stream():
        yield f"data: {json.dumps({'type': 'version', 'content': 'LLM_SQL_AGENT_V2_FROM_SSE'})}\n\n"

        async for chunk in stream_copilot(query=query, db=db):
            yield chunk

    return StreamingResponse(
        debug_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "X-Copilot-Version": "LLM_SQL_AGENT_V2_FROM_SSE",
        },
    )


# ─────────────────────────────────────────────────────────────
# INSIGHTS ENDPOINTS
# ─────────────────────────────────────────────────────────────
@router.get("/insights/dashboard", response_model=InsightOut)
async def dashboard_insights(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return InsightOut(insights=await build_dashboard_insights(db))


@router.get("/insights/products/{sku}", response_model=InsightOut)
async def product_insights(
    sku: str,
    warehouse_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return InsightOut(insights=await build_product_recommendations(db, sku, warehouse_id))


@router.get("/insights/forecast", response_model=InsightOut)
async def forecast_insights(
    warehouse: str | None = None,
    category: str | None = None,
    period: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return InsightOut(insights=await build_forecast_commentary(db, warehouse, category, period))