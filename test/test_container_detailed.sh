#!/bin/bash

echo "🔬 TESTE DETALHADO - ANÁLISE DE STATUS DO CONTAINER"
echo "=================================================="

# Função para testar um cenário específico
test_container_scenario() {
    local title="$1"
    local alertname="$2"
    local status="$3"
    local value="$4"
    local container_name="$5"
    local host_ip="$6"
    
    echo ""
    echo "🧪 TESTANDO: $title"
    echo "--------------------"
    echo "Alert: $alertname | Status: $status | Value: $value"
    
    curl -s -X POST "http://localhost:5001/alert_minimal" \
         -H "Content-Type: text/plain" \
         -d "CONTAINER_ALERT_START
alertname: $alertname
status: $status
startsAt: $(date -Iseconds)
instance: $host_ip:8080
job: cadvisor
prometheus_server: prometheus-test
host_ip: $host_ip
real_host: $host_ip:8080
service_type: container-metrics
environment: test
container: $container_name
container_name: $container_name
namespace: test-namespace
node: test-node
image: $container_name:latest
value_A: $value
valuestring: value=$value
CONTAINER_ALERT_END"
    
    sleep 1
}

echo ""
echo "🎯 Cenários de Teste:"
echo "1. Container definitivamente DOWN (firing + value=0)"
echo "2. Container definitivamente UP (resolved + value=1)"
echo "3. Container em transição (firing + value=1 - pode estar reiniciando)"
echo "4. Container problemático (resolved + value=0 - estado inconsistente)"

# Teste 1: Container DOWN clássico
test_container_scenario \
    "Container DOWN Clássico" \
    "ContainerDown" \
    "firing" \
    "0" \
    "webapp-frontend" \
    "192.168.1.100"

# Teste 2: Container UP resolvido
test_container_scenario \
    "Container UP Resolvido" \
    "ContainerUp" \
    "resolved" \
    "1" \
    "webapp-backend" \
    "192.168.1.101"

# Teste 3: Container em transição (pode estar reiniciando)
test_container_scenario \
    "Container Reiniciando" \
    "ContainerRestarting" \
    "firing" \
    "1" \
    "database-mysql" \
    "192.168.1.102"

# Teste 4: Estado inconsistente
test_container_scenario \
    "Estado Inconsistente" \
    "ContainerIssue" \
    "resolved" \
    "0" \
    "cache-redis" \
    "192.168.1.103"

# Teste 5: Container com nome específico do seu ambiente
test_container_scenario \
    "Container Ambiente Real" \
    "ContainerDown" \
    "firing" \
    "0" \
    "nginx-web-server" \
    "192.168.1.200"

echo ""
echo "✅ TESTES FINALIZADOS!"
echo "====================="
echo ""
echo "📊 Resultados Esperados:"
echo "✅ Container DOWN Clássico → DEVE ALERTAR"
echo "❌ Container UP Resolvido → NÃO deve alertar"
echo "⚠️ Container Reiniciando → Pode alertar (firing)"
echo "🤔 Estado Inconsistente → Não deve alertar (resolved)"
echo "✅ Container Ambiente Real → DEVE ALERTAR"
echo ""
echo "🔍 Para monitorar em tempo real:"
echo "docker compose logs -f grafana-discord-proxy"