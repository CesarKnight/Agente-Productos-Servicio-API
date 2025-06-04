import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

LLM_MODEL = str("gpt-4o-mini")
EMBEDDING_MODEL = str("text-embedding-3-large")
MODEL_TEMPERATURE = float(os.getenv("MODEL_TEMPERATURE", "0.5"))

OPENAI_API_KEY = str(os.getenv("OPENAI_API_KEY"))

# Configuración pase de datos
CHECKPOINTER_DATABASE_PATH = str(Path.cwd() / "databases/checkpointer.db")

POSTGRES_USER = os.getenv("POSTGRES_USER", "user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
POSTGRES_DB = os.getenv("POSTGRES_DB", "default")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))

# Comportamiento del agente
MAX_MESSAGES_BEFORE_SUMMARY = int(os.getenv("MAX_MESSAGES_BEFORE_SUMMARY", "6"))

# Configuración de debug
DEBUG = os.getenv("DEBUG", "False").lower() == "true"