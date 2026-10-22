#!/usr/bin/env bash
set -euo pipefail

docker compose exec rag-service python -m RAG.build_index --reset
echo "Knowledge base reset."
sleep 3