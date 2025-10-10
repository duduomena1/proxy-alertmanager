#!/bin/bash

echo "🧪 Testando Alertas de CPU e Memória com Debug Ativado"
echo "======================================================"

# Aguarda o container inicializar
echo "Aguardando container inicializar..."
sleep 3

# Testa alerta de CPU
echo ""
echo "1. 🖥️ Testando alerta de CPU..."
curl -X POST http://localhost:5001/alert -H "Content-Type: application/json" -d '{
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "HighCPUUsage",
        "job": "node-exporter",
        "instance": "192.168.255.248:9100",
        "service_type": "node"
      },
      "annotations": {
        "description": "O uso da CPU atingiu > 50%",
        "summary": "CPU alta detectada"
      },
      "values": {
        "A": 67.7
      },
      "valueString": "value=67.7",
      "startsAt": "2025-10-10T17:41:50Z"
    }
  ]
}'

echo ""
echo "2. 💾 Testando alerta de Memória..."
curl -X POST http://localhost:5001/alert -H "Content-Type: application/json" -d '{
  "alerts": [
    {
      "status": "firing", 
      "labels": {
        "alertname": "HighMemoryUsage",
        "job": "node-exporter",
        "instance": "192.168.255.248:9100",
        "service_type": "node"
      },
      "annotations": {
        "description": "O uso da Memória atingiu > 50%",
        "summary": "Memória alta detectada"
      },
      "values": {
        "A": 67.7
      },
      "valueString": "value=67.7",
      "startsAt": "2025-10-10T06:39:00Z"
    }
  ]
}'

echo ""
echo "3. 💿 Testando alerta de Disco (para comparação)..."
curl -X POST http://localhost:5001/alert -H "Content-Type: application/json" -d '{
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "HighDiskUsage", 
        "job": "node-exporter",
        "instance": "192.168.255.248:9100",
        "device": "/dev/sda1",
        "mountpoint": "/",
        "service_type": "node"
      },
      "annotations": {
        "description": "O uso do disco está acima de 90%",
        "summary": "Disco quase cheio"
      },
      "values": {
        "A": 90.4
      },
      "valueString": "value=90.4",
      "startsAt": "2025-10-10T17:41:50Z"
    }
  ]
}'

echo ""
echo "✅ Testes enviados! Agora vamos verificar os logs de debug:"
echo ""
echo "📊 Verificando logs do container..."
sleep 2

docker compose logs --tail=50 grafana-discord-proxy | grep -E "(DEBUG|ERROR|extract_metric_value|Alert Type)"

echo ""
echo "🎯 Verifique também no Discord:"
echo "   - CPU deve mostrar: 67.7%"
echo "   - Memória deve mostrar: 67.7%"  
echo "   - Disco deve mostrar: 90.4%"
echo ""
echo "Se os valores não estiverem corretos, verifique os logs de debug acima!"