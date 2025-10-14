# Configurações de teste para containers
# Execute: source test_config.sh

export PROXY_URL="http://localhost:5001"
export DEBUG_MODE="true"
export TEST_WEBHOOK_URL="https://discord.com/api/webhooks/YOUR_TEST_WEBHOOK"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Função helper para testes
test_alert() {
    local alertname="$1"
    local status="$2"
    local value="$3"
    local container="$4"
    local host="$5"
    
    echo -e "${BLUE}🧪 Testando:${NC} $alertname | Status: $status | Value: $value | Container: $container"
    
    curl -s -X POST "$PROXY_URL/alert_minimal" \
         -H "Content-Type: text/plain" \
         -d "CONTAINER_ALERT_START
alertname: $alertname
status: $status
startsAt: $(date -Iseconds)
instance: $host:8080
container_name: $container
host_ip: $host
value_A: $value
valuestring: value=$value
CONTAINER_ALERT_END"
    
    sleep 0.5
}

# Função para verificar se o proxy está rodando
check_proxy() {
    if curl -s "$PROXY_URL/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Proxy está rodando em $PROXY_URL${NC}"
        return 0
    else
        echo -e "${RED}❌ Proxy não está acessível em $PROXY_URL${NC}"
        echo "Execute: docker compose up -d"
        return 1
    fi
}

# Função para testar conectividade do Discord
test_discord() {
    if [ -n "$DISCORD_WEBHOOK_URL" ]; then
        echo "🔗 Testando conectividade com Discord..."
        curl -s -X POST "$DISCORD_WEBHOOK_URL" \
             -H "Content-Type: application/json" \
             -d '{"content":"🧪 Teste de conectividade do proxy Grafana"}' && \
        echo -e "${GREEN}✅ Discord webhook funcionando${NC}" || \
        echo -e "${RED}❌ Erro no Discord webhook${NC}"
    else
        echo -e "${YELLOW}⚠️ DISCORD_WEBHOOK_URL não configurado${NC}"
    fi
}

echo "🔧 Configurações de teste carregadas!"
echo "Comandos disponíveis:"
echo "  check_proxy     - Verifica se o proxy está rodando"
echo "  test_discord    - Testa conectividade com Discord"
echo "  test_alert      - Função helper para testes rápidos"
echo ""
echo "Exemplo de uso:"
echo "  test_alert 'ContainerDown' 'firing' '0' 'nginx' '192.168.1.100'"