from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ChatMessage(BaseModel):
    role: str = Field(..., description="user or assistant")
    content: str

class CopilotChatRequest(BaseModel):
    conversation_history: List[ChatMessage] = []
    current_prompt: str = Field(..., examples=["What should I reorder this week?"])
    active_page_context: Optional[str] = Field(None, description="Pass active page module to focus LLM context window.")

class CopilotChatResponse(BaseModel):
    generated_reply: str
    executed_tools: List[str] = []
    extracted_metrics: Dict[str, Any] = {}