from fastapi import HTTPException

from src.utils.response_models import ChatRequest, ChatResponse
from src.services.langgraph_service import get_graph , query_graph

async def process_chat_query(request: ChatRequest) -> ChatResponse:
    """
    Procesa una consulta de chat y devuelve una respuesta.
    """
    langgrafo = get_graph()

    if langgrafo is None:
        raise HTTPException(status_code=500, detail="El grafo no ha sido inicializado correctamente.")
    
    try:
        response = await query_graph(request.query, request.chat_id)
        return ChatResponse(
            query=request.query,
            chat_id=response["chat_id"],
            interest=response["interest"],
            element_id=response["element_id"],
            respuesta=response["respuesta"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar la consulta: {str(e)}")