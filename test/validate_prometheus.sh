#!/bin/bash

# 🧪 Script de Validação da Configuração Prometheus
# Executa testes para verificar se as melhorias estão funcionando

echo "======================================================================="
echo "🧪 VALIDAÇÃO DA CONFIGURAÇÃO PROMETHEUS"
echo "======================================================================="

# Configurações
PROMETHEUS_URL="http://localhost:9090"
EXPECTED_LABELS=("real_host" "host_ip" "prometheus_server" "service_type")

echo ""
echo "📋 1. VERIFICANDO STATUS DO PROMETHEUS..."

# Verifica se Prometheus está rodando
if curl -s "$PROMETHEUS_URL/-/healthy" > /dev/null; then
    echo "✅ Prometheus está rodando"
else
    echo "❌ Prometheus não está acessível em $PROMETHEUS_URL"
    echo "   Verifique se o serviço está rodando"
    exit 1
fi

echo ""
echo "📋 2. VERIFICANDO TARGETS..."

# Verifica targets
TARGETS_RESPONSE=$(curl -s "$PROMETHEUS_URL/api/v1/targets" | python3 -c "
import sys, json
data = json.load(sys.stdin)
active_targets = data['data']['activeTargets']
print(f'Total targets: {len(active_targets)}')
for target in active_targets:
    job = target['labels']['job']
    health = target['health']
    endpoint = target['scrapeUrl']
    print(f'  {job}: {health} - {endpoint}')
")

echo "$TARGETS_RESPONSE"

echo ""
echo "📋 3. VERIFICANDO NOVOS LABELS..."

# Verifica se os novos labels estão presentes
for label in "${EXPECTED_LABELS[@]}"; do
    echo -n "  Verificando label '$label'... "
    
    QUERY_RESULT=$(curl -s "$PROMETHEUS_URL/api/v1/query?query=up{$label!=\"\"}" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data['status'] == 'success' and data['data']['result']:
        print('FOUND')
    else:
        print('NOT_FOUND')
except:
    print('ERROR')
")
    
    if [ "$QUERY_RESULT" = "FOUND" ]; then
        echo "✅ Encontrado"
    else
        echo "❌ Não encontrado"
    fi
done

echo ""
echo "📋 4. TESTANDO QUERY DE EXEMPLO..."

# Testa query específica
echo "Query: up{job=\"node-exporter\"}"
curl -s "$PROMETHEUS_URL/api/v1/query?query=up{job=\"node-exporter\"}" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data['status'] == 'success':
        results = data['data']['result']
        print(f'Resultados encontrados: {len(results)}')
        for result in results:
            labels = result['metric']
            print('  Labels disponíveis:')
            for key, value in labels.items():
                if key in ['instance', 'real_host', 'host_ip', 'prometheus_server', 'job']:
                    print(f'    {key}: {value}')
            print('')
    else:
        print('Query falhou')
except Exception as e:
    print(f'Erro ao processar resposta: {e}')
"

echo ""
echo "📋 5. SIMULAÇÃO DE ALERTA..."

# Simula como o alerta apareceria
echo "Exemplo de como os labels aparecerão nos alertas:"
echo ""
curl -s "$PROMETHEUS_URL/api/v1/query?query=up{job=\"node-exporter\"}" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data['status'] == 'success' and data['data']['result']:
        result = data['data']['result'][0]['metric']
        
        print('📊 DADOS DO ALERTA:')
        print(f'  instance: {result.get(\"instance\", \"N/A\")}')
        print(f'  real_host: {result.get(\"real_host\", \"N/A\")}')
        print(f'  host_ip: {result.get(\"host_ip\", \"N/A\")}')
        print(f'  prometheus_server: {result.get(\"prometheus_server\", \"N/A\")}')
        print(f'  service_type: {result.get(\"service_type\", \"N/A\")}')
        print('')
        
        # Simula template
        host_ip = result.get('host_ip', result.get('instance', 'unknown').split(':')[0])
        prometheus_source = result.get('prometheus_server', 'unknown')
        
        print('📝 TEMPLATE RESULTANTE:')
        print(f'  alertname: Disk Alert - {host_ip}')
        print(f'  server: {host_ip}')
        print(f'  prometheus_source: {prometheus_source}')
        print(f'  status: RESOLVED ✅')
        
    else:
        print('❌ Nenhum resultado encontrado')
except Exception as e:
    print(f'Erro: {e}')
"

echo ""
echo "======================================================================="
echo "📋 RESUMO DA VALIDAÇÃO"
echo "======================================================================="

# Resumo final
curl -s "$PROMETHEUS_URL/api/v1/query?query=up{job=\"node-exporter\"}" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data['status'] == 'success' and data['data']['result']:
        result = data['data']['result'][0]['metric']
        
        # Verifica se melhorias foram aplicadas
        has_real_host = 'real_host' in result
        has_host_ip = 'host_ip' in result
        has_prometheus_server = 'prometheus_server' in result
        
        print('✅ PROBLEMAS RESOLVIDOS:')
        if has_host_ip:
            print('  ✅ IP Real identificado:', result.get('host_ip'))
        else:
            print('  ❌ IP Real ainda não identificado')
            
        if has_prometheus_server:
            print('  ✅ Fonte Prometheus identificada:', result.get('prometheus_server'))
        else:
            print('  ❌ Fonte Prometheus não identificada')
            
        if has_real_host:
            print('  ✅ Host original preservado:', result.get('real_host'))
        else:
            print('  ❌ Host original não preservado')
            
        print('')
        success_rate = sum([has_real_host, has_host_ip, has_prometheus_server]) / 3 * 100
        print(f'📊 Taxa de Sucesso: {success_rate:.0f}%')
        
        if success_rate == 100:
            print('🎉 CONFIGURAÇÃO APLICADA COM SUCESSO!')
        elif success_rate >= 50:
            print('⚠️  CONFIGURAÇÃO PARCIALMENTE APLICADA')
            print('   Restart o Prometheus e execute novamente')
        else:
            print('❌ CONFIGURAÇÃO NÃO APLICADA')
            print('   Verifique o arquivo prometheus.yaml')
            
    else:
        print('❌ Não foi possível verificar as melhorias')
        print('   Certifique-se que o node-exporter está rodando')
except Exception as e:
    print(f'Erro na validação: {e}')
"

echo ""
echo "🔧 Para aplicar as configurações:"
echo "   1. cp prometheus_updated.yaml prometheus.yaml"
echo "   2. docker-compose restart prometheus"
echo "   3. ./validate_prometheus.sh"