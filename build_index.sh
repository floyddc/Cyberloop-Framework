#!/usr/bin/env bash
set -euo pipefail

docker compose exec rag-service python -m RAG.build_index
echo "Knowledge base indexed!"
sleep 3