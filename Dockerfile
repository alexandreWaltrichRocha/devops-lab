# ---- Estágio 1: builder (instala dependências) ----
FROM python:3.11-alpine AS builder
WORKDIR /app
COPY app/requirements.txt .
RUN pip install --no-cache-dir --target=/install -r requirements.txt

# ---- Estágio 2: runner (imagem final enxuta) ----
FROM python:3.11-alpine AS runner

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY --from=builder /install /usr/local/lib/python3.11/site-packages
COPY app/ .

# UID numérico: o Kubernetes só consegue validar `runAsNonRoot: true` quando o
# USER da imagem é numérico (com nome ele recusa o pod).
RUN addgroup -S -g 10001 appgroup && adduser -S -u 10001 -G appgroup appuser
USER 10001

EXPOSE 8000

# Usado pelo Docker/Compose (o Kubernetes ignora e usa suas próprias probes).
# Python no lugar de curl: a imagem alpine não traz curl.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" || exit 1

# --no-access-log: a própria app registra cada requisição em JSON (com rota, status e duração).
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
