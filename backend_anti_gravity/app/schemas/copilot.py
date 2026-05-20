"""
schemas/copilot.py — Pydantic v2 schemas for the LLM Copilot endpoint.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CopilotRequest(BaseModel):
    """Natural language query submitted to the copilot reasoning engine."""
    query: str = Field(..., min_length=3, max_length=2000,
        description="Free-text question in natural language")
    context: Optional[Dict[str, Any]] = Field(
        None, description="Optional structured context to pre-seed the reasoning loop"
    )
    stream: bool = Field(default=False, description="If true, returns SSE streaming response")


class ToolCall(BaseModel):
    """Represents a single database tool invoked by the LLM reasoning loop."""
    tool_name: str
    parameters: Dict[str, Any] = {}
    result_summary: Optional[str] = None


class CopilotResponse(BaseModel):
    """Structured copilot response with data evidence and narrative."""
    query: str
    intent: str = Field(..., description="Detected intent category")
    tools_invoked: List[ToolCall] = []
    data_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Raw structured data retrieved from the database"
    )
    narrative: str = Field(..., description="LLM-generated human-readable explanation")
    confidence: float = Field(..., ge=0.0, le=1.0,
        description="Reasoning confidence score 0.0–1.0")
    follow_up_suggestions: List[str] = []


class StreamChunk(BaseModel):
    """Individual SSE chunk for streaming responses."""
    type: str  # "tool_call" | "narrative" | "done" | "error"
    content: str
    metadata: Optional[Dict[str, Any]] = None
