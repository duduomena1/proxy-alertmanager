#!/bin/bash

echo "🔧 REBUILD RÁPIDO - Corrigindo Erro do Flask"
echo "=============================================="

echo "⏹️  Parando containers..."
docker compose down

echo "🧹 Limpando cache Docker..."
docker system prune -f

echo "🔨 Fazendo rebuild..."
docker compose build --no-cache

echo "🚀 Subindo container..."
docker compose up -d

echo "⏳ Aguardando inicialização..."
sleep 15

echo "🔍 Verificando status..."
docker compose ps

echo "📋 Verificando logs..."
docker compose logs grafana-discord-proxy --tail=10

echo ""
echo "🏥 Testando health check..."
if curl -f -s http://localhost:5001/health; then
    echo "✅ Sucesso! Container funcionando"
else
    echo "❌ Ainda com problemas. Logs completos:"
    docker compose logs grafana-discord-proxy
fi

echo ""
echo "📊 Para monitorar em tempo real:"
echo "docker compose logs grafana-discord-proxy -f"