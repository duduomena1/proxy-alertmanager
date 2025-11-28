
# Dockerfile Simplificado - Discord Proxy

FROM python:3.11-slim

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

## Copia requirements primeiro para cache de build
COPY requirements.txt ./

## Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt

## Copia código da aplicação modular
COPY app ./app
COPY main.py ./
## Copia configs (inclui portainer_endpoints.json)
COPY config ./config

# Configurações de produção
ENV FLASK_APP=main.py
ENV PYTHONPATH=/app
ENV DEBUG_MODE=false
ENV FLASK_ENV=production

# Cria usuário não-root e diretório de dados
RUN adduser --disabled-password --gecos '' --uid 1000 appuser && \
    chown -R appuser:appuser /app && \
    mkdir -p /app/data && \
    chown -R appuser:appuser /app/data

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:5001/health || exit 1

USER appuser

EXPOSE 5001

# Comando para produção (ponto de entrada modular)
CMD ["python", "-u", "main.py"]