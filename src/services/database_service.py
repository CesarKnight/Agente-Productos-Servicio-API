from langchain_community.utilities  import SQLDatabase

import src.configs.consts as consts    

username = consts.POSTGRES_USER
password = consts.POSTGRES_PASSWORD
host = consts.POSTGRES_HOST
port = consts.POSTGRES_PORT
database = consts.POSTGRES_DB

# Globals
dbEngine = None

#initialization function
def init_db_engine():
    global dbEngine
    if not dbEngine:
        dbEngine = SQLDatabase.from_uri(
            f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{database}"
        )
    return dbEngine

def get_db_engine():
    global dbEngine
    if dbEngine is None:
        dbEngine = init_db_engine()
    return dbEngine

def list_tables():
    """List all tables in the database."""
    if dbEngine is None:
        raise ValueError("Database engine is not initialized. Call init_db_engine() first.")
    return dbEngine.get_usable_table_names()

def get_schema():
    """Get the schema of the database."""
    if dbEngine is None:
        raise ValueError("Database engine is not initialized. Call init_db_engine() first.")
    return dbEngine.get_table_info()