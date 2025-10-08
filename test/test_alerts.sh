#!/bin/bash

# Script para testar o Grafana Discord Proxy
# Este script envia exemplos de alertas para testar a funcionalidade

PROXY_URL="http://localhost:5001/alert"

echo "🧪 Testando Grafana Discord Proxy com Sistema de Severidade..."
echo "URL: $PROXY_URL"
echo

# Teste 1: Alerta de Disco Original
echo "📀 Testando alerta de DISCO (Original)..."
curl -X POST "$PROXY_URL" \
  -H "Content-Type: application/json" \
  -d @disco.json \
  -w "\nStatus: %{http_code}\n"
echo

sleep 2

# Teste 2: Alerta de CPU Original
echo "🖥️ Testando alerta de CPU (Original)..."
curl -X POST "$PROXY_URL" \
  -H "Content-Type: application/json" \
  -d @cpu.json \
  -w "\nStatus: %{http_code}\n"
echo

sleep 2

# Teste 3: Alerta de Memória Original
echo "� Testando alerta de MEMÓRIA (Original)..."
curl -X POST "$PROXY_URL" \
  -H "Content-Type: application/json" \
  -d @memoria.json \
  -w "\nStatus: %{http_code}\n"
echo

sleep 2

# Teste 4: Nível CRÍTICO (90-100%)
echo "🔥 Testando alerta de Nível CRÍTICO (95.5%)..."
curl -X POST "$PROXY_URL" \
  -H "Content-Type: application/json" \
  -d @test_high_level.json \
  -w "\nStatus: %{http_code}\n"
echo

sleep 2

# Teste 5: Nível ALERTA (80-89%)
echo "🚧 Testando alerta de Nível ALERTA (84.2%)..."
curl -X POST "$PROXY_URL" \
  -H "Content-Type: application/json" \
  -d @test_medium_level.json \
  -w "\nStatus: %{http_code}\n"
echo

sleep 2

# Teste 6: Nível ATENÇÃO (0-79%)
echo "⚠️ Testando alerta de Nível ATENÇÃO (72.3%)..."
curl -X POST "$PROXY_URL" \
  -H "Content-Type: application/json" \
  -d @test_low_level.json \
  -w "\nStatus: %{http_code}\n"
echo

sleep 2

# Teste 7: Container DOWN
echo "🚨 Testando alerta de CONTAINER DOWN..."
curl -X POST "$PROXY_URL" \
  -H "Content-Type: application/json" \
  -d @test_container_down.json \
  -w "\nStatus: %{http_code}\n"
echo

sleep 2

# Teste 8: Container UP (Resolved)
echo "✅ Testando alerta de CONTAINER UP (Resolvido)..."
curl -X POST "$PROXY_URL" \
  -H "Content-Type: application/json" \
  -d @test_container_up.json \
  -w "\nStatus: %{http_code}\n"
echo

sleep 2

# Teste 9: Health Check
echo "🔍 Testando Health Check..."
curl -X GET "http://localhost:5001/health" \
  -H "Content-Type: application/json" \
  -w "\nStatus: %{http_code}\n"
echo

echo "✅ Testes concluídos!"
echo ""
echo "📊 Resumo dos testes realizados:"
echo "   📀 Disco Original (83.3%) - Nível ALERTA"
echo "   🖥️ CPU Original (48.2%) - Nível ATENÇÃO"  
echo "   💾 Memória Original (26.9%) - Nível ATENÇÃO"
echo "   🔥 Disco Crítico (95.5%) - Nível CRÍTICO"
echo "   🚧 CPU Alerta (84.2%) - Nível ALERTA"
echo "   ⚠️ Memória Atenção (72.3%) - Nível ATENÇÃO"
echo "   🚨 Container DOWN - CONTAINER OFFLINE"
echo "   ✅ Container UP - CONTAINER ONLINE"
echo ""
echo "Verifique seu canal do Discord para ver os alertas com diferentes:"
echo "   • Cores baseadas no nível de severidade"
echo "   • GIFs específicos para cada combinação"
echo "   • Emojis indicando o nível de criticidade"
echo "   • Tratamento especial para containers (UP/DOWN)"