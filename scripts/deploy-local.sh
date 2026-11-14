#!/usr/bin/env bash
# Build local + deploy no Minikube, com tag única (evita imagem velha em cache).
# Uso: ./scripts/deploy-local.sh        (se precisar: DOCKER_HOST=unix:///var/run/docker.sock ./scripts/deploy-local.sh)
set -euo pipefail
cd "$(dirname "$0")/.."

grep -q '"/health"' app/main.py || { echo "ERRO: app/main.py sem /health (código antigo?)" >&2; exit 1; }

BASE_IMAGE="alexandrew2033/devops-lab"
IMG="${BASE_IMAGE}:local-$(date +%Y%m%d%H%M%S)"

docker build -t "$IMG" .
minikube image load "$IMG"

# Tudo menos o Deployment da API (que vai com a tag imutável, logo abaixo).
for f in k8s/*.yml; do
  [[ "$f" == "k8s/deployment.yml" ]] && continue
  kubectl apply -f "$f"
done

# O manifesto traz `:latest` só como valor padrão. Aqui ele é trocado pela tag única
# ANTES do apply, então o cluster nunca recebe `latest` e há um único rollout.
RENDERED="$(sed "s|image: ${BASE_IMAGE}:latest|image: ${IMG}|" k8s/deployment.yml)"
grep -q "image: ${IMG}" <<<"$RENDERED" || { echo "ERRO: não achei a imagem no deployment.yml" >&2; exit 1; }
kubectl apply -f - <<<"$RENDERED"

kubectl rollout status deployment/devops-lab-deployment --timeout=180s

echo
echo "Pronto: $IMG"
echo "Acesse com:  kubectl port-forward svc/devops-lab-service 8080:80   ->  http://localhost:8080"
