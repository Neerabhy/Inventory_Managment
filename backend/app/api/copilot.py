from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.models.auth import User
from app.schemas.copilot import CopilotChatRequest, CopilotChatResponse
from app.services.copilot_agent import CopilotOrchestrator

router = APIRouter(prefix="/copilot", tags=["AI Copilot Interface"])

@router.post("/chat", response_model=CopilotChatResponse)
async def process_copilot_chat(
    request: CopilotChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Enterprise LLM entry point. Parses intent, triggers backend data tools, 
    and returns a professionally formatted business explanation.
    """
    try:
        # Instantiate the orchestration engine with the active DB session
        orchestrator = CopilotOrchestrator(db_session=db)
        
        # Process the chat loop
        response_data = await orchestrator.process_chat(
            user_prompt=request.current_prompt,
            history=[msg.model_dump() for msg in request.conversation_history]
        )
        
        return CopilotChatResponse(
            generated_reply=response_data.get("generated_reply", ""),
            executed_tools=response_data.get("executed_tools", []),
            extracted_metrics={}
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to communicate with AI Reasoning Engine: {str(e)}"
        )