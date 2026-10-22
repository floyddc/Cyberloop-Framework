#!/usr/bin/env bash
set -euo pipefail

ROOT="$(python3 -c 'import os; print(os.getcwd())')"
cd "$ROOT"

docker compose up -d postgres
python3 -m pip install psycopg2-binary

export PYTHONPATH="$ROOT/python"
export KNOWLEDGE_DIR="$ROOT/knowledge"
export POSTGRES_HOST="127.0.0.1"
export POSTGRES_PORT="5432"
export POSTGRES_USER="cyberresponse"
export POSTGRES_PASSWORD="cyberresponse"
export POSTGRES_KNOWLEDGE_DB="knowledge"

python3 -c 'import socket; socket.create_connection(("127.0.0.1", 5432), timeout=5).close(); print("PostgreSQL online")'

python3 -m postgres.seed_knowledge_base
sleep 3