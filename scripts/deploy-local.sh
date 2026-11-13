#!/usr/bin/env bash
# Build local + deploy no Minikube, com tag única (evita imagem velha em cache).
# Uso: ./scripts/deploy-local.sh        (se precisar: DOCKER_HOST=unix:///var/run/docker.sock ./scripts/deploy-local.sh)
set -euo pipefail
cd "$(dirname "$0")/.."

grep -q '"/health"' app/main.py || { echo "ERRO: app/main.py sem /health (código antigo?)" >&2; exit 1; }

IMG="alexandrew2033/devops-lab:local-$(date +%Y%m%d%H%M%S)"

docker build -t "$IMG" .
minikube image load "$IMG"

kubectl apply -f k8s/
kubectl set image deployment/devops-lab-deployment devops-lab="$IMG"
kubectl rollout status deployment/devops-lab-deployment --timeout=180s

echo
echo "Pronto: $IMG"
echo "Acesse com:  kubectl port-forward svc/devops-lab-service 8080:80   ->  http://localhost:8080"
