#!/usr/bin/env bash
# Teste de carga contra a stack local (Docker Compose, porta 80) usando k6 em container.
# Uso: ./scripts/loadtest.sh                 # 60 req/s por 60s
#      RATE=90 DURATION=2m ./scripts/loadtest.sh
#      BASE_URL=http://localhost:8080 ./scripts/loadtest.sh   # via port-forward do Kubernetes
# Acompanhe em paralelo o dashboard do Grafana (http://localhost:3000).
set -euo pipefail
cd "$(dirname "$0")/.."

# --network host: o container enxerga o localhost da máquina (Linux/WSL2).
docker run --rm -i --network host \
  -e BASE_URL="${BASE_URL:-http://localhost}" \
  -e RATE="${RATE:-60}" \
  -e DURATION="${DURATION:-60s}" \
  grafana/k6:0.54.0 run - < loadtest/k6.js
