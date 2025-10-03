#!/bin/bash

# Script para testar o Grafana Discord Proxy
# Este script envia exemplos de alertas para testar a funcionalidade

PROXY_URL="http://localhost:5001/alert"

echo "🧪 Testando Grafana Discord Proxy..."
echo "URL: $PROXY_URL"
echo

# Teste 1: Alerta de Disco
echo "📀 Testando alerta de DISCO..."
curl -X POST "$PROXY_URL" \
  -H "Content-Type: application/json" \
  -d @disco.json \
  -w "\nStatus: %{http_code}\n"
echo

# Aguarda um pouco entre os testes
sleep 2

# Teste 2: Alerta de CPU  
echo "🖥️ Testando alerta de CPU..."
curl -X POST "$PROXY_URL" \
  -H "Content-Type: application/json" \
  -d @cpu.json \
  -w "\nStatus: %{http_code}\n"
echo

# Aguarda um pouco entre os testes
sleep 2

# Teste 3: Alerta de Memória
echo "💾 Testando alerta de MEMÓRIA..."
curl -X POST "$PROXY_URL" \
  -H "Content-Type: application/json" \
  -d @memoria.json \
  -w "\nStatus: %{http_code}\n"
echo

# Teste 4: Health Check
echo "🔍 Testando Health Check..."
curl -X GET "http://localhost:5001/health" \
  -H "Content-Type: application/json" \
  -w "\nStatus: %{http_code}\n"
echo

echo "✅ Testes concluídos!"
echo "Verifique seu canal do Discord para ver os alertas."