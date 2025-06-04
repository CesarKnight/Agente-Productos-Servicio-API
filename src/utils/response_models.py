from pydantic import BaseModel
from typing import Optional, Literal

class ChatRequest(BaseModel):
    query: str
    chat_id : Optional[str] = None

class ChatResponse(BaseModel):
    chat_id: str
    interest: Literal["producto","variante","promocion", "categoria", ""]
    element_id : str
    query: str
    respuesta: str