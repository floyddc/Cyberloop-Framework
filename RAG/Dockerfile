FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/python \
    KNOWLEDGE_DIR=/app/knowledge \
    CACHE_DIR=/models

WORKDIR /app

COPY RAG/service-requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        torch==2.14.0+cpu \
    && pip install --no-cache-dir -r /tmp/requirements.txt
    
COPY RAG /app/RAG
COPY python/config.py /app/python/config.py
COPY python/retrieve_agent.py /app/python/retrieve_agent.py
COPY postgres/db.py /app/postgres/db.py
RUN mkdir -p /app/knowledge/indices /models

EXPOSE 8000

CMD ["uvicorn", "RAG.api:app", "--host", "0.0.0.0", "--port", "8000"]
