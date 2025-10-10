#!/bin/bash

echo "🎯 VALIDAÇÃO FINAL - Alertas CPU, Memória e Disco"
echo "================================================="

echo ""
echo "📊 Enviando alertas com valores específicos para comparação:"

echo ""
echo "1. 🖥️  CPU: 85.5%"
curl -s -X POST http://localhost:5001/alert -H "Content-Type: application/json" -d '{
  "alerts": [{
    "status": "firing",
    "labels": {
      "alertname": "HighCPUUsage",
      "job": "node-exporter", 
      "instance": "192.168.255.248:9100",
      "service_type": "node"
    },
    "annotations": {
      "description": "CPU usage is high at 85.5%",
      "summary": "High CPU detected"
    },
    "values": {"A": 85.5},
    "valueString": "value=85.5",
    "startsAt": "2025-10-10T12:30:00Z"
  }]
}' > /dev/null

echo "   ✅ Enviado"

echo ""
echo "2. 💾 Memória: 72.3%"
curl -s -X POST http://localhost:5001/alert -H "Content-Type: application/json" -d '{
  "alerts": [{
    "status": "firing",
    "labels": {
      "alertname": "HighMemoryUsage",
      "job": "node-exporter",
      "instance": "192.168.255.248:9100", 
      "service_type": "node"
    },
    "annotations": {
      "description": "Memory usage is high at 72.3%",
      "summary": "High memory detected"
    },
    "values": {"A": 72.3},
    "valueString": "value=72.3",
    "startsAt": "2025-10-10T12:30:00Z"
  }]
}' > /dev/null

echo "   ✅ Enviado"

echo ""
echo "3. 💿 Disco: 95.8%"
curl -s -X POST http://localhost:5001/alert -H "Content-Type: application/json" -d '{
  "alerts": [{
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
      "description": "Disk usage is critical at 95.8%",
      "summary": "Disk almost full"
    },
    "values": {"A": 95.8},
    "valueString": "value=95.8", 
    "startsAt": "2025-10-10T12:30:00Z"
  }]
}' > /dev/null

echo "   ✅ Enviado"

echo ""
echo "🔍 Verificando logs das últimas mensagens:"
sleep 2
docker compose logs --tail=15 grafana-discord-proxy | grep -E "(Uso atual|Final extracted value|Sent.*alert)"

echo ""
echo "🎯 VERIFIQUE NO DISCORD:"
echo "   CPU deve mostrar: 85.5%"
echo "   Memória deve mostrar: 72.3%"
echo "   Disco deve mostrar: 95.8%"
echo ""
echo "✅ Se os valores acima estão corretos no Discord, o problema foi RESOLVIDO!"
echo "❌ Se ainda estão incorretos, há algo específico no seu ambiente de produção."