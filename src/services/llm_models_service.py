from langchain_openai import ChatOpenAI
import src.configs.consts as consts

# Globals
embeddings = None
llm = None

# Initialization functions
def init_llm():
    global llm
    if not llm:
        llm = ChatOpenAI(model=consts.LLM_MODEL, temperature=consts.MODEL_TEMPERATURE)
    return llm

# Getter functions
def get_llm():
    global llm
    if llm is None:
        llm = init_llm()
    return llm