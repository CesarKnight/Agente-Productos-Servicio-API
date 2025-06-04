from typing import Annotated, Sequence
from typing_extensions import TypedDict
from uuid import uuid4
import sqlite3, json

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph, START
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.runnables import RunnableConfig

import src.configs.consts as consts
import src.services.nodes_service as nodes
import src.services.edges_service as edges
import src.services.llm_models_service as llm_models

# Constantes
embeddings_model = consts.EMBEDDING_MODEL
openai_model = consts.LLM_MODEL
checkpointer_db_path = consts.CHECKPOINTER_DATABASE_PATH
model_temperature = consts.MODEL_TEMPERATURE

llm = llm_models.init_llm()
# grafo global
graph = None

async def initialize_checkpointer_db() -> SqliteSaver:
    # Conexión a la base de datos para el checkpointer
    try: 
        db_path = checkpointer_db_path
        conn = sqlite3.connect(db_path, check_same_thread=False)
        memory = SqliteSaver(conn)    
    except Exception as e:
        raise RuntimeError(f"Error initializing checkpointer database: {e}")
    
    return memory

# Estado del agente para el almacenamiento de mensajes y resumen 
class AgentState(TypedDict):
    """Estado del agente."""
    last_question: str
    last_query: str
    last_query_result: str 
    
    summary: str
    messages: Annotated[Sequence[BaseMessage], add_messages]

async def initialize_graph():
    # Inicializamos los modelos y herramientas
    global graph
    memory = await initialize_checkpointer_db()

    query_call_node = ToolNode([nodes.query_call])

    builder = StateGraph(AgentState)

    builder.add_node("agent", nodes.agent)
    builder.add_node("query_call", query_call_node)
    builder.add_node("reformulate_question", nodes.reformulate_question)
    builder.add_node("generate_query", nodes.generate_query)
    builder.add_node("run_query", nodes.run_query)
    builder.add_node("detect_interest", nodes.detect_interest)
    builder.add_node("generate_response", nodes.generate_response)
    builder.add_node("summarize", nodes.summarize)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges(
        "agent",
        tools_condition,
        {
            "tools": "query_call",
            END: END
        }
    )
    builder.add_edge("query_call", "reformulate_question")
    builder.add_edge("reformulate_question", "generate_query")
    builder.add_edge("generate_query", "run_query")
    builder.add_edge("run_query", "detect_interest")
    builder.add_edge("detect_interest", "generate_response")
    builder.add_conditional_edges(
        "generate_response",
        edges.summarize_condition,
        {
            "summarize": "summarize",
            END: END
        }
    )
    builder.add_edge("summarize", END)

    graph = builder.compile(checkpointer=memory)
    
def get_graph() -> CompiledStateGraph:
    if graph is None:
        raise RuntimeError("Graph not initialized. Call initialize_graph() first.")
    
    return graph

async def query_graph(query: str, chat_id: str | None = None ) -> dict:
    """
    Recibe la consulta e id de chat, en caso de no recibir id de chat se genera uno nuevo.
    Args:
        query (str): Consulta a realizar al grafo.
        chat_id (str, optional): ID del chat. Si no se proporciona, se genera uno nuevo.
    returns:
        dict: {
            "message": respuesta,
            "chat_id": id del chat
        }
    """
    if graph is None:
        await initialize_graph()
        
    if chat_id is None :
        while True:
            chat_id = str(uuid4())
            # Verifica si el chat_id ya existe en la base de datos
            config: RunnableConfig = {"configurable": {"thread_id": chat_id}}
            if not graph.checkpointer.get(config):
                break
        
    config: RunnableConfig = {"configurable": {"thread_id": chat_id}}
    try:
        question_message = HumanMessage(content=query)
        output_messages = graph.invoke({"messages": [question_message]}, config=config) #type: ignore
        last_message = output_messages["messages"][-1]
        try:
            data = json.loads(last_message.content)
        except json.JSONDecodeError:
            data = {}
            
        interest = data.get("interest", "")
        element_id = data.get("element_id", "")
        response = data.get("response", "")
        
        print(f" chat_id: {chat_id}\n interest: {interest}\n element_id: {element_id}\n response: {response}")
        
        return {"interest": interest,"element_id": element_id ,"respuesta": response, "chat_id": chat_id}
    except Exception as e:
        raise RuntimeError(f"Error querying the graph: {e}")