#!/bin/bash

echo "🔧 REBUILD RÁPIDO - Grafana Discord Proxy"
echo "=========================================="

echo "⏹️  Parando containers..."
docker compose down

echo "🔨 Fazendo rebuild..."
docker compose build

echo "🚀 Subindo container..."
docker compose up -d

echo "⏳ Aguardando inicialização..."
sleep 5

echo "🔍 Verificando status..."
docker compose ps

echo ""
echo "💾 Verificando persistência..."
if docker exec grafana-discord-proxy-prod ls /app/data/suppression-state.json &>/dev/null; then
    echo "✅ Estado de supressão persistido em ./data/"
else
    echo "⚠️  Arquivo de supressão não encontrado (será criado no primeiro alerta)"
fi

echo ""
echo "🏥 Testando health check..."
if curl -f -s http://localhost:5001/health &>/dev/null; then
    echo "✅ Sucesso! Container funcionando"
else
    echo "⚠️  Health check falhou (aguardando inicialização completa)"
fi

echo ""
echo "📊 Para monitorar em tempo real:"
echo "docker compose logs grafana-discord-proxy-prod -f"