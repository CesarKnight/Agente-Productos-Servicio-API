from fastapi import APIRouter
from src.controllers.chat_controller import process_chat_query
from src.utils.response_models import ChatRequest, ChatResponse

router = APIRouter(prefix="/api", tags=["chat"])

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Endpoint para procesar consultas de chat sobre el reglamento de tránsito.
    """
    return await process_chat_query(request)
