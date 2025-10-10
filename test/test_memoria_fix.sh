#!/bin/bash

echo "🧪 Teste Específico para Alerta de Memória"
echo "=========================================="

# Ativa debug temporariamente
echo "Ativando debug temporário..."
docker compose exec grafana-discord-proxy sh -c 'export DEBUG_MODE=true'

# Aguarda
sleep 2

echo ""
echo "📧 Enviando alerta de memória com dados simulados do seu ambiente:"

curl -X POST http://localhost:5001/alert -H "Content-Type: application/json" -d '{
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "Memory - Tatico2",
        "job": "node-exporter",
        "instance": "192.168.255.248:9100",
        "service_type": "node",
        "prometheus_server": "prometheus-main",
        "host_ip": "192.168.255.248"
      },
      "annotations": {
        "description": "O uso da Memória atingiu > 50%",
        "summary": "Memória alta no servidor Tatico2"
      },
      "values": {
        "A": 67.9
      },
      "valueString": "value=67.9",
      "startsAt": "2025-10-09T17:41:50Z"
    }
  ]
}'

echo ""
echo "✅ Alerta enviado!"

echo ""
echo "📊 Verificando logs de debug:"
sleep 2
docker compose logs --tail=15 grafana-discord-proxy | grep -E "(DEBUG|extract_real_ip_and_source|prometheus_source|real_ip)"

echo ""
echo "🎯 Verifique no Discord se agora aparece:"
echo "   Servidor: 192.168.255.248" 
echo "   Prometheus: prometheus-main"
echo "   Uso atual: 67.9%"