# Servicio de API de agente para consultas con la BD
## Dev:

Instalar dependencias con uv:
```cmd
uv sync
```

Correr dev:
```
fastapi dev src/main.py
```

# Production:
```
uvicorn main:app --port 8000 --reload
```