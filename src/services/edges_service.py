from pydantic import BaseModel, Field
from typing import  Literal

from langgraph.graph import END

import src.configs.consts as consts
import src.services.llm_models_service as llm_models


#Edges son aristas que se ejecutan entre los nodos en un lang-grafo.

max_messages_before_summary = consts.MAX_MESSAGES_BEFORE_SUMMARY

llm = llm_models.get_llm()

def summarize_condition(state) -> Literal["summarize", END]: #type: ignore
    messages = state.get("messages", [])
    if len(messages) > max_messages_before_summary:
        return "summarize"
    return END