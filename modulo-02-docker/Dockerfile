# Estágio 1: Builder (Instalação e compilação de dependências)
FROM python:3.11-alpine AS builder

WORKDIR /app

COPY app/requirements.txt .
RUN pip install --no-cache-dir --target=/install -r requirements.txt

# Estágio 2: Runner (Imagem final limpa e segura)
FROM python:3.11-alpine AS runner

WORKDIR /app

# Copia as bibliotecas instaladas
COPY --from=builder /install /usr/local/lib/python3.11/site-packages
COPY app/ .

# Boas Práticas SRE: Criar e usar usuário não-privilegiado
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

EXPOSE 8000

# Correção: Invocamos o uvicorn como módulo do python (-m)
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
