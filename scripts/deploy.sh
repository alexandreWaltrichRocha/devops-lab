#!/usr/bin/env bash
# Deploy no cluster usando uma imagem JÁ PUBLICADA pelo CI no Docker Hub, com tag
# imutável (sha-<commit>). Faz rollback automático se o rollout não completar.
#
# Uso:
#   ./scripts/deploy.sh                 # tag = sha-<commit atual>  (o CI precisa ter terminado)
#   ./scripts/deploy.sh sha-<40 hex>    # tag específica (ex.: v1.2.3 também funciona)
#   ./scripts/deploy.sh --rollback      # volta para a revisão anterior
set -euo pipefail
cd "$(dirname "$0")/.."

BASE_IMAGE="alexandrew2033/devops-lab"
DEPLOY="deployment/devops-lab-deployment"

if [[ "${1:-}" == "--rollback" ]]; then
  kubectl rollout undo "$DEPLOY"
  kubectl rollout status "$DEPLOY" --timeout=180s
  echo "Rollback concluído. Imagem atual:"
  kubectl get "$DEPLOY" -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
  exit 0
fi

TAG="${1:-sha-$(git rev-parse HEAD)}"
[[ "$TAG" == "latest" ]] && { echo "ERRO: não faça deploy de :latest (sem rastreabilidade)." >&2; exit 1; }
IMG="${BASE_IMAGE}:${TAG}"

if [[ -z "${1:-}" && -n "$(git status --porcelain)" ]]; then
  echo "AVISO: há alterações locais; a imagem ${TAG} reflete só o commit, não o seu working tree." >&2
fi

echo "Deploy de ${IMG}"
for f in k8s/*.yml; do
  [[ "$f" == "k8s/deployment.yml" ]] && continue
  kubectl apply -f "$f"
done
RENDERED="$(sed "s|image: ${BASE_IMAGE}:latest|image: ${IMG}|" k8s/deployment.yml)"
grep -q "image: ${IMG}" <<<"$RENDERED" || { echo "ERRO: não achei a imagem no deployment.yml" >&2; exit 1; }
kubectl apply -f - <<<"$RENDERED"

if ! kubectl rollout status "$DEPLOY" --timeout=180s; then
  echo "Rollout falhou: revertendo para a revisão anterior..." >&2
  kubectl rollout undo "$DEPLOY"
  kubectl rollout status "$DEPLOY" --timeout=180s || true
  exit 1
fi
echo "Pronto: ${IMG}"
