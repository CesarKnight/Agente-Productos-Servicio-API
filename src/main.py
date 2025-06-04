from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from src.services.langgraph_service import initialize_graph

from src.routes import chat_route

@asynccontextmanager
async def lifespan(app: FastAPI):
    """ Inicializar servicio
    """
    await initialize_graph()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Asistente Legal API",
    description="API para consultar información sobre el reglamento de tránsito boliviano",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(router=chat_route.router)

@app.get("/")
async def root():
    return {"mensaje": "Bienvenido a la API del Asistente Legal"}