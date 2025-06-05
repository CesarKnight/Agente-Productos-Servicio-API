import json, ast, re
from typing import TypedDict, Annotated

from langchain_core.messages import RemoveMessage, SystemMessage, AIMessage
from langchain_core.tools import tool

import src.services.llm_models_service as llm_models
import src.configs.consts as consts
import src.services.database_service as db_service

from langchain_core.messages import  SystemMessage, AIMessage, FunctionMessage, HumanMessage, RemoveMessage
from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool

@tool(return_direct=True)
def query_call ():
    """Just a call to the query tool."""
    
tools = [query_call]
llm = llm_models.get_llm()
dbEngine = db_service.get_db_engine()
tables_schema = dbEngine.get_table_info()

def agent(state):
    """
    El agente determina si se necesita usar la herramienta de query o responde con la info actual.
    Construye una lista de mensajes para el LLM en vez de un solo prompt.
    """
    messages = []
    question = state.get("messages")[-1].content
    last_question = state.get("last_question", "")
    last_query_result = state.get("last_query_result", "")
    last_query = state.get("last_query", "")

    # Mensaje de sistema base
    base_sys_msg = (
        "Eres un agente de marketing especializado en ofrecer productos y responder preguntas sobre caracteristicas,precios, categorias, variantes y promociones u ofertas. "
        "Cuentas con una herramienta que te permite consultar a la base de datos de productos para responder preguntas del cliente. "
        "Se te presentará con una pregunta la cual debes llamar a la herramienta en caso que el usuario pida "
        "Si el cliente menciona que desea comprar el producto menciona que puede visitar la tienda o el sitio web para realizar la compra. "
        "En caso que la pregunta sea una confirmacion o sea evidente que falte contexto usa la herramienta. "
        "En caso que la pregunta no sea sobre productos, promociones, precios o caracteristicas , responde amigable y brevemente sin usar la herramienta. "
        "En caso que sí se necesita usar la herramienta, no pidas autorización al usuario, simplemente llama a la herramienta de consulta."
    )
    messages.append(SystemMessage(content=base_sys_msg))

    # Si hay resultado de query previo, añade contexto relevante
    if last_question:
        messages.append(SystemMessage(content="Usa la respuesta del query anterior y el resumen actual para responder si es posible."))
        messages.append(SystemMessage(content=f"Pregunta anterior: {last_question}"))
        messages.append(SystemMessage(content=f"Anterior query: {last_query}"))
        messages.append(SystemMessage(content=f"Resultado del query: {last_query_result}"))
        messages.append(SystemMessage(content="Si el sql query anterior no cubrió la pregunta del usuario, usa la herramienta para hacer un nuevo query."))
    else:
        messages.append(SystemMessage(content="Si necesitas información para la pregunta usa la herramienta."))

    # Añade la pregunta del usuario
    messages.append(HumanMessage(content=question))

    model = llm.bind_tools(tools)
    response = model.invoke(messages)
    
    result = {
        "response": response.content
    }
    
    response.content = json.dumps(result, ensure_ascii=False)
    
    return {"messages": [response]}


def needs_reformulation(current_question, last_question):
    # If the current question is a greeting or generic, treat as new topic
    generic_starts = ["ofreces", "ofrece", "ofrecen", "puedes mostrarme", "hola", "buenos dias", "productos", "cosas", "promociones", "articulos"]
    # Check if any generic word appears anywhere in the question (not just at the start)
    if any(g in current_question.lower() for g in generic_starts):
        return False
    # If the current question is a follow-up (e.g., has "y", "además", etc.), reformulate
    follow_ups = ["y", "además", "con", "sin", "de",     "otra vez", "opciones", "variantes", "caracteristicas", "precio", "promocion", "especificaciones"]
    if any(g in current_question.lower() for g in follow_ups):
        return False
    # If the last question is empty, don't reformulate
    if not last_question:
        return False
    # Default: reformulate
    return True

def reformulate_question(state: AgentState):
    """
    Antes de generar un query, se reformula la pregunta del usuario en base a la anterior pregunta, resumen y query.
    aqui se guarda la pregunta como ultima pregunta
    """
    messages = state.get("messages", [])
    
    last_question = state.get("last_question", "")
    last_query = state.get("last_query", "")
    last_response = messages[-4].content if len(messages) >= 4 and hasattr(messages[-4], "content") else ""
    current_question = messages[-3].content if len(messages) >= 3 and hasattr(messages[-3], "content") else ""
    summary = state.get("summary", "")
    
    if not needs_reformulation(current_question, last_question):
        return {"last_question": current_question, "messages": [HumanMessage(content=current_question)]}

    # Build message list for LLM: last question, last response, last query
    reformulation_messages = []
    if last_question:
        reformulation_messages.append(HumanMessage(content=f"Pregunta anterior: {last_question}"))
    if last_response:
        reformulation_messages.append(AIMessage(content=f"Respuesta anterior: {last_response}"))
    if last_query:
        reformulation_messages.append(SystemMessage(content=f"Query anterior: {last_query}"))

    # If not enough recent context, add summary
    if len(reformulation_messages) < 2 and summary:
        reformulation_messages.append(SystemMessage(content=f"Resumen de la conversación: {summary}"))

    prompt = (
        "Reformula la siguiente pregunta del usuario de manera breve,concisa y sin acentos para consultar a nuestra base de datos de productos "
        "los parametros de reformulacion tienen peso en el orden de importancia: "
        "1. anterior respuesta del llm, 2. anterior pregunta del usuario, 3. query anterior, 4. Resumen de la conversación.\n"
        "No tomar en cuenta la respuesta anterior o pregunta anterior si no es relevante para la pregunta actual. "
        "Si no hay suficiente contexto reciente, usa el resumen."
    )
    reformulation_messages.append(SystemMessage(content=prompt))
    
    reformulation_messages.append(HumanMessage(content=current_question))
    reformulated = llm.invoke(reformulation_messages)
        
    return {"last_question": reformulated.content ,"messages": [reformulated]}

class QueryOutput(TypedDict):
    """Generated SQL query."""

    query: Annotated[str, ..., "Syntactically valid SQL query."]


def generate_query(state):
    """" Genera un query SQL a partir de una pregunta del usuario y el schema de la base de datos. """
    question = state.get("last_question", "")
    
    schema_message = SystemMessage(content=tables_schema)
    generate_query_system_prompt = f"""
    Dada las tablas de la base de datos, solo usa las disponibles.
    Se proveera una pregunta de entrada, crea una consulta {dbEngine.dialect} sintácticamente correcta para ayudar a encontrar la respuesta. 
    Puedes ordenar los resultados por una columna relevante para devolver los ejemplos más interesantes de la base de datos.

    Al devolver cualquier precio solo pide con concepto "precio consumidor" a menos que se especifique lo contrario.
    No uses la descripcion de variante para buscar caraceristicas, usa la tabla caraceristica y tipo_caracteristica para buscar las caracteristicas de variantes.
    En caso que se consulte por las variantes, caracteristicas o especificaciones de un producto, devuelve solo el id del producto, nombre del producto, descripcion de variante y caracteristicas.
    En caso que se consulte por un producto con cierta caracteristica, busca la variante de ese producto que tenga el valor de caracteristica pedido y devuelve el id de variante, nombre del producto, descripcion de variante, caracteristicas y precios.
    
    En caso de consulta por todos los productos,devuelve los productos con id, nombre, descripcion.
    En caso que se consulte por el precio de una promocion o solo una promocion, devuelve la promocion entera estrictamente con ID, la variante relacionada a traves de oferta_articulo y el nombre de producto, no devuelvas las ids de variante ni producto.
    En caso que se consulte por promociones, devuelve las promociones enteras con ID y con las variantes relacionadas a traves de la tabla intermedia oferta_articulo, ademas devuelve el nombre del producto, no devuelvas las ids de variante ni producto.
    En caso de que se consulte por categorias, devuelve la categoria con sus productos y variantes.

    Presta atención a usar solo los nombres de columnas que aparecen en la descripción del esquema.
    Ten cuidado de no consultar columnas que no existen. Además, asegúrate de saber qué columna pertenece a qué tabla.
    """
    sys_message = SystemMessage(content=generate_query_system_prompt)
    
    question_message = HumanMessage(content=question)
    prompt_messages = [schema_message, sys_message, question_message]
    
    structured_llm = llm.with_structured_output(QueryOutput)
    response = structured_llm.invoke(prompt_messages)
    
    query = response.get("query", "")
    query_message = AIMessage(content=query)
    return {"last_query": query, "messages": [query_message]}

def run_query(state):
    """Execute SQL query."""
    messages = state.get("messages", [])
    query = state.get("last_query", "")
    
    execute_query_tool = QuerySQLDatabaseTool(db=dbEngine)

    result = execute_query_tool.invoke(query)
    result_message = FunctionMessage(name="Sql_query", content=result)
    return {"last_query_result": result, "messages": [result_message]}

class InterestOutput(TypedDict):
    """Formato para el resultado de deteccion de interes"""

    interest: Annotated[str, ..., "A table name of the type of interest (e.g., 'producto', 'variante', 'categoria', 'promocion')"]
    
def detect_interest(state):
    """" Detecta el tipo de elemento del que se habla, en caso que sea solo un elemento entre:
    producto, variante, categoria o promocion devuelve un mensaje con el formato: interest: <tipo> id: <id>"""
    
    question_message = HumanMessage(content=state.get("last_question", ""))
    last_query_message = AIMessage(content=state.get("last_query", ""))
    last_query_result = state.get("last_query_result", "")
    last_query_result_message = FunctionMessage(name="Sql_query", content=last_query_result)
    # Para pillar el interes buscamos ids unicos, si solo hay uno es interes
    # Regex para extraer UUIDs
    uuid_regex = r"UUID\('([a-f0-9\-]{36})'\)"
    ids = re.findall(uuid_regex, str(last_query_result))
    unique_ids = set(ids)

    # Si solo hay un id único, lo consideramos interés
    element_id = ""
    if len(unique_ids) == 1 and len(ids) > 0:
        element_id = list(unique_ids)[0]
    else:
        element_id = ""
    
    # si hay mas de un id, no se puede determinar interes
    if not element_id:
        result = {"interest": "", "element_id": ""}
        return {"messages": [AIMessage(content=json.dumps(result, ensure_ascii=False))]}
    
    
    prompt = """Detecta el tipo de elemento del que se habla, entre las tablas: producto, variante, categoria o promocion.
    Si se pregunta por las caraceristicas de un producto, devuelve 'producto'.
    Si se pregunta por las variantes disponibles de un producto, devuelve 'producto'.
    Si se pregunta por las caracteristicas o precio, especificamente de una variante especifica de producto, devuelve 'variante'."""
    sys_message = SystemMessage(content=prompt)
    messages_list = [question_message, last_query_message, last_query_result_message ,sys_message]
    
    structured_llm = llm.with_structured_output(InterestOutput)
    response = structured_llm.invoke(messages_list)
    
    interest = response.get("interest", "")
    result = {"interest": interest, "element_id": element_id}
    
    response_message = AIMessage(content=json.dumps(result, ensure_ascii=False))
    
    return{"messages": [response_message]}

def generate_response(state):
    """Generate a response based on the last query result and the summary."""
    
    interest = ""
    element_id = ""
    
    last_message = state.get("messages")[-1]
    
    content = last_message.content
    if isinstance(content, dict):
        if "interest" in content and "element_id" in content:
            interest = content["interest"]
            element_id = content["element_id"]
           
    elif isinstance(content, str):
        # Intenta parsear si es un string con formato dict
        parsed = ast.literal_eval(content)
        if isinstance(parsed, dict) and "interest" in parsed and "element_id" in parsed:
            interest = parsed["interest"]
            element_id = parsed["element_id"]

        
    question = state.get("last_question", "")
    last_query_result = state.get("last_query_result", "")
    
    prompt_message_list = []
    
    if(last_query_result):
        prompt_message_list.append(FunctionMessage(content=last_query_result, name="Sql_query"))
        prompt = """Actua como agente de marketing, 
        nunca respondas con ids, en caso que se consulte por promocion no modifiques la respuesta de ninguna manera
        usa unicamente el resultado de query para responder la pregunta:"""
    else:
        prompt = """No se obtuvo un resultado de query, responde a la pregunta unicamente ofreciendo realizar otra busqueda con diferentes valores del parametro consultado o generalizar la busqueda."""
    
    prompt_message_list.append(SystemMessage(content=prompt)) 
    prompt_message_list.append(HumanMessage(content=question))
    
    response = llm.invoke(prompt_message_list)
    
    result = {
        "interest": interest,
        "element_id": element_id,
        "response": response.content
    }

    # Devuelve como mensaje para el grafo
    return {"messages": [AIMessage(content=json.dumps(result, ensure_ascii=False))]}

def summarize(state):
    """Summarize the conversation."""
    messages = state.get("messages", [])
    summary = state.get("summary", "")
    
    if summary:
        prompt = f"Este es el resumen actual de la conversación:\n{summary}\n\nExpande el resumen incluyendo los puntos clave y las preguntas realizadas en 3 oraciones, sin incluir respuestas o resultados de consultas SQL."
    else: 
        prompt = "Resume la conversación pasada de manera concisa y clara, incluyendo los puntos clave y las preguntas realizadas en 3 oraciones, sin incluir respuestas o resultados de consultas SQL."
        
    summary_message = HumanMessage(content=prompt)    
    summary_response = llm.invoke(messages + [summary_message]) # type: ignore
    new_summary = summary_response.content
    
    delete_messages = [RemoveMessage(id=m.id) for m in messages][:-1]
    
    return {"summary": new_summary, "messages": delete_messages}