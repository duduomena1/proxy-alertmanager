#!/bin/bash

echo "🧪 TESTE ESPECÍFICO - ALERTAS DE CONTAINER DOWN vs UP"
echo "=================================================="

# Definir URLs do proxy
PROXY_MINIMAL_URL="http://localhost:5001/alert_minimal"

echo ""
echo "🔴 1. TESTANDO CONTAINER DOWN (deve alertar)..."
echo "----------------------------------------------"

curl -s -X POST $PROXY_MINIMAL_URL -H "Content-Type: text/plain" -d '
CONTAINER_ALERT_START
alertname: ContainerDown
status: firing
startsAt: 2025-10-14T18:45:00Z
instance: 192.168.1.200:8080
job: cadvisor
prometheus_server: prometheus-main
host_ip: 192.168.1.200
real_host: 192.168.1.200:8080
service_type: container-metrics
environment: production
__address__: 192.168.1.200:8080
prometheus: prometheus-main
container: nginx-web-server
container_name: nginx-web-server
namespace: web-services
node: worker-node-01
image: nginx:1.21-alpine
value_A: 0
valuestring: value=0
CONTAINER_ALERT_END'

echo ""
echo "🟢 2. TESTANDO CONTAINER UP (NÃO deve alertar)..."
echo "------------------------------------------------"

curl -s -X POST $PROXY_MINIMAL_URL -H "Content-Type: text/plain" -d '
CONTAINER_ALERT_START
alertname: ContainerUp
status: resolved
startsAt: 2025-10-14T18:46:00Z
instance: 192.168.1.200:8080
job: cadvisor
prometheus_server: prometheus-main
host_ip: 192.168.1.200
real_host: 192.168.1.200:8080
service_type: container-metrics
environment: production
__address__: 192.168.1.200:8080
prometheus: prometheus-main
container: nginx-web-server
container_name: nginx-web-server
namespace: web-services
node: worker-node-01
image: nginx:1.21-alpine
value_A: 1
valuestring: value=1
CONTAINER_ALERT_END'

echo ""
echo "🔴 3. TESTANDO OUTRO CONTAINER DOWN com mais detalhes..."
echo "------------------------------------------------------"

curl -s -X POST $PROXY_MINIMAL_URL -H "Content-Type: text/plain" -d '
CONTAINER_ALERT_START
alertname: ContainerUnavailable
status: firing
startsAt: 2025-10-14T18:47:00Z
instance: 192.168.1.201:8080
job: cadvisor
prometheus_server: prometheus-cluster-02
host_ip: 192.168.1.201
real_host: 192.168.1.201:8080
service_type: container-metrics
environment: production
__address__: 192.168.1.201:8080
prometheus: prometheus-cluster-02
container: mysql-database
container_name: mysql-database
pod: mysql-db-pod-xyz123
namespace: database
node: worker-node-02
kubernetes_node: worker-node-02
image: mysql:8.0.32
container_image: mysql:8.0.32
value_A: 0
valuestring: value=0
CONTAINER_ALERT_END'

echo ""
echo "🚨 4. TESTANDO CONTAINER PROBLEMÁTICO (status firing mas value=1)..."
echo "------------------------------------------------------------------"

curl -s -X POST $PROXY_MINIMAL_URL -H "Content-Type: text/plain" -d '
CONTAINER_ALERT_START
alertname: ContainerHighMemory
status: firing
startsAt: 2025-10-14T18:48:00Z
instance: 192.168.1.202:8080
job: cadvisor
prometheus_server: prometheus-main
host_ip: 192.168.1.202
real_host: 192.168.1.202:8080
service_type: container-metrics
environment: staging
__address__: 192.168.1.202:8080
prometheus: prometheus-main
container: redis-cache
container_name: redis-cache
namespace: cache
node: worker-node-03
image: redis:7-alpine
value_A: 1
valuestring: value=1
CONTAINER_ALERT_END'

echo ""
echo "✅ TESTES CONCLUÍDOS!"
echo "===================="
echo ""
echo "📋 O que deve acontecer:"
echo "1. ✅ Container DOWN (value=0) → DEVE ALERTAR"
echo "2. ❌ Container UP (value=1, resolved) → NÃO deve alertar"  
echo "3. ✅ Container DOWN com detalhes → DEVE ALERTAR"
echo "4. ⚠️ Container problemático (firing) → Pode alertar"
echo ""
echo "📊 Verifique:"
echo "- Logs do proxy: docker compose logs -f grafana-discord-proxy"
echo "- Mensagens no Discord (apenas containers DOWN devem aparecer)"
echo ""
echo "🔍 Para debug:"
echo "export DEBUG_MODE=true"
echo "docker compose restart grafana-discord-proxy"