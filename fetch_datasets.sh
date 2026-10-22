#!/usr/bin/env bash
set -euo pipefail

ROOT="$(python3 -c 'import os; print(os.getcwd())')"
cd "$ROOT"

if [[ -f "$ROOT/.env" ]]; then
    set -a
    source "$ROOT/.env"
    set +a
fi
python3 -c 'import os; print("HF_TOKEN set:", bool(os.getenv("HF_TOKEN")))'

export PYTHONPATH="$ROOT/python"
export KNOWLEDGE_DIR="$ROOT/knowledge"

python3 -c "import config; print(config.KNOWLEDGE_DIR)"
python3 -m knowledge.fetch_datasets
sleep 3