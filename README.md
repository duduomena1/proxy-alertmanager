# 🚀 Grafana Discord Proxy

Um proxy inteligente e avançado para enviar alertas do Grafana para o Discord com análise automatizada de containers, templates flexíveis e formatação elegante.

## ✨ Características Principais

- 🧠 **Análise Inteligente de Containers**: Detecta automaticamente status DOWN/UP e filtra alertas desnecessários
- 🎯 **Duplo Endpoint**: Suporte para alertas JSON padrão (`/alert`) e templates minimalistas (`/alert_minimal`)
- 🎨 **Templates Personalizáveis**: Templates Grafana livres de erros de função (`float64`, `regex`, etc.)
- 📱 **Formatação Rica**: Mensagens organizadas com informações detalhadas do ambiente
- 🐳 **Container Ready**: Análise específica para Kubernetes, Docker Swarm e containers standalone
- 🔧 **Configuração Flexível**: Variáveis de ambiente para todas as personalizações
- 🔍 **Debug Avançado**: Logs detalhados para troubleshooting e análise

## 🚦 Tipos de Alertas Suportados

| Tipo | Emoji | Detecta por | Análise Especial |
|------|--------|-------------|------------------|
| **CPU** | 🖥️ | `cpu`, `processor`, `load` | Extração automática de valores % |
| **Memória** | 💾 | `memory`, `mem`, `ram` | Conversão de bytes para % |
| **Disco** | 💿 | `disk`, `storage`, `filesystem` | Device e mountpoint detalhados |
| **Container** | 🐳 | `container`, `docker`, `pod` | **Status inteligente DOWN/UP** |
| **Padrão** | 🚨 | Outros tipos | Processamento genérico |

## � Sistema Inteligente de Containers

### Análise Automática de Status

O proxy analisa automaticamente o status dos containers baseado em múltiplos fatores:

```python
# Critérios de análise:
- value=0 + status=firing  → Container DOWN (ALERTA)
- value=1 + status=resolved → Container UP (IGNORA)
- value=0 + status=resolved → Container RECOVERING (IGNORA)
- value=1 + status=firing → Container INSTÁVEL (ALERTA)
```

### Informações Detalhadas

Para containers DOWN, o sistema coleta automaticamente:

- 🏷️ **Nome do Container**: `nginx-web-server`
- 🖥️ **Node/Host**: `worker-node-01` 
- � **Namespace**: `web-services`
- 🎯 **IP da VM**: `192.168.1.200`
- 📷 **Imagem**: `nginx:1.21-alpine`
- ⚙️ **Job**: `cadvisor`
- � **Prometheus**: `prometheus-main`

## 🎯 Endpoints Disponíveis

### 1. `/alert` - Endpoint Principal (Recomendado)
```yaml
# Grafana Contact Point
url: http://seu-proxy:5001/alert
method: POST
content-type: application/json
```
**Uso**: Alertas padrão do Grafana em formato JSON completo

### 2. `/alert_minimal` - Endpoint para Templates
```yaml
# Grafana Contact Point com template customizado
url: http://seu-proxy:5001/alert_minimal
method: POST
content-type: text/plain

# Template exemplo:
CONTAINER_ALERT_START
alertname: {{ .CommonLabels.alertname }}
status: {{ .Status }}
container_name: {{ .CommonLabels.container }}
host_ip: {{ .CommonLabels.host_ip }}
value_A: {{ range .Alerts }}{{ .Values.A }}{{ end }}
CONTAINER_ALERT_END
```
**Uso**: Quando você precisa de controle total sobre os dados enviados

### 3. `/health` - Health Check
```bash
curl http://seu-proxy:5001/health
# Retorna: {"service":"grafana-discord-proxy","status":"ok"}
```

## 📋 Pré-requisitos

- Docker e Docker Compose
- Webhook do Discord configurado
- Grafana 8.0+ com Contact Points configurados
- Prometheus com métricas de container (cadvisor, kubelet, etc.)

## ⚙️ Instalação e Configuração

### 1. Clone e Configure

```bash
git clone https://github.com/duduomena1/proxy-alertmanager.git
cd proxy-alertmanager

# Copie o arquivo de exemplo
cp .env.example .env

# Edite as configurações
nano .env
```

### 2. Configure o Webhook do Discord

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/SEU_WEBHOOK_AQUI
DEBUG_MODE=false
APP_PORT=5001
```

### 3. Execute com Docker

```bash
# Build e start
docker-compose up -d

# Verificar logs
docker-compose logs -f grafana-discord-proxy

# Verificar status
docker-compose ps
```

### 4. Configure o Grafana

#### Opção A: Alertas Padrão (Simples)
```yaml
# Contact Point no Grafana
Type: Webhook
URL: http://IP_DO_SERVIDOR:5001/alert
HTTP Method: POST
```

#### Opção B: Com Template Customizado
```yaml
# Contact Point no Grafana  
Type: Webhook
URL: http://IP_DO_SERVIDOR:5001/alert_minimal
HTTP Method: POST

# Use os templates em /templates/ para evitar erros
```

## 📁 Templates Prontos

O projeto inclui templates testados e livres de erros:

```
templates/
├── container-template-minimal.yml    # Template para containers
├── CPU-template .yml                 # Template para CPU
├── memory-template-minimal.yml       # Template para memória  
├── disk-template-minimal.yml         # Template para disco
└── prometheus.yaml                   # Config do Prometheus
```

### Exemplo de Template de Container

```yaml
# container-template-minimal.yml
CONTAINER_ALERT_START
alertname: {{ .CommonLabels.alertname }}
status: {{ .Status }}
startsAt: {{ .Alerts.StartsAt }}
container: {{ .CommonLabels.container }}
container_name: {{ .CommonLabels.container_name }}
namespace: {{ .CommonLabels.namespace }}
node: {{ .CommonLabels.node }}
host_ip: {{ .CommonLabels.host_ip }}
image: {{ .CommonLabels.image }}
value_A: {{ range .Alerts }}{{ .Values.A }}{{ end }}
CONTAINER_ALERT_END
```

## 🧪 Testes Automatizados

O projeto inclui um conjunto completo de testes:

```bash
test/
├── test_alerts.sh              # Teste geral de alertas
├── test_container_down_vs_up.sh # Teste específico containers
├── test_container_detailed.sh   # Análise detalhada containers
├── test_config.sh              # Configurações de teste
├── validacao_final.sh          # Validação completa
└── *.json                      # Payloads de teste
```

### Executando Testes

```bash
# Teste específico de containers
./test/test_container_down_vs_up.sh

# Teste detalhado com análise
./test/test_container_detailed.sh

# Teste geral
./test/test_alerts.sh
```

## 📊 Exemplos de Saída

### Alerta de Container DOWN

```text
🐳 **CONTAINER CRÍTICO** 🔴

**Container:** `nginx-web-server`
**Status:** Container está PARADO e não responde
**Severidade:** `CRÍTICO`

📦 **Namespace:** `web-services`
🖥️ **Node:** `worker-node-01`
⚙️ **Job:** `cadvisor`
🏷️ **Image:** `nginx:1.21-alpine`

⏰ **Início:** 2025-10-14T18:45:00Z
🔧 **Config:** Prometheus: prometheus-main | Job: cadvisor | Env: production
```

### Alerta de Disco

```text
� **DISCO ALERTA** �

📊 **Uso de DISCO:** 83.3% (🚧 ALERTA)
🖥️ **Servidor:** 192.168.1.100
💾 **Device:** /dev/sda1
📁 **Mountpoint:** /var/lib/docker

⏰ **Início:** 2025-10-14T18:45:00Z
🔧 **Config:** Prometheus: prometheus-main | Service: node-exporter
```

## 🔧 Configuração Avançada

### Variáveis de Ambiente

```env
# Básico
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
DEBUG_MODE=false
APP_PORT=5001

# Cores por Severidade (formato decimal)
CPU_LOW_COLOR=16776960          # Amarelo
CPU_MEDIUM_COLOR=16753920       # Laranja  
CPU_HIGH_COLOR=16711680         # Vermelho

# GIFs por Tipo de Alerta
CPU_LOW_GIF=https://giphy.com/...
MEMORY_MEDIUM_GIF=https://giphy.com/...
CONTAINER_DOWN_GIF=https://giphy.com/...
```

### Configuração do Docker Compose

```yaml
# docker-compose.yml
services:
  grafana-discord-proxy:
    build: .
    ports:
      - "5001:5001"
    environment:
      - DEBUG_MODE=true
    networks:
      - grafana_observability
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5001/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## 🐳 Deploy em Produção

### Com Docker Swarm

```bash
# Deploy no swarm
docker stack deploy -c docker-compose.yml grafana-proxy

# Verificar serviços
docker service ls
```

### Com Kubernetes

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: grafana-discord-proxy
spec:
  replicas: 2
  selector:
    matchLabels:
      app: grafana-discord-proxy
  template:
    spec:
      containers:
      - name: proxy
        image: grafana-discord-proxy:latest
        ports:
        - containerPort: 5001
        env:
        - name: DISCORD_WEBHOOK_URL
          valueFrom:
            secretKeyRef:
              name: discord-secret
              key: webhook-url
```

### Monitoramento e Logs

```bash
# Logs em tempo real
docker-compose logs -f grafana-discord-proxy

# Métricas do container
docker stats grafana-discord-proxy-prod

# Health check
curl -s http://localhost:5001/health | jq
```

## 🛠️ Desenvolvimento

### Setup Local

```bash
# Clonar repositório
git clone https://github.com/duduomena1/proxy-alertmanager.git
cd proxy-alertmanager

# Ambiente virtual Python
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows

# Instalar dependências
pip install -r requirements.txt

# Executar em modo desenvolvimento
export DEBUG_MODE=true
export DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
python discord_proxy.py
```

### Estrutura de Arquivos

```text
proxy-alertmanager/
├── discord_proxy.py           # 🐍 Aplicação Flask principal
├── requirements.txt           # 📦 Dependências Python
├── Dockerfile                 # 🐳 Configuração do container
├── docker-compose.yml         # 🚀 Orquestração dos serviços
├── .env.example              # ⚙️ Exemplo de configurações
├── rebuild.sh                # 🔧 Script de rebuild automático
├── templates/                # 📄 Templates do Grafana
│   ├── container-template-minimal.yml
│   ├── CPU-template .yml
│   ├── memory-template-minimal.yml
│   ├── disk-template-minimal.yml
│   └── prometheus.yaml
├── test/                     # 🧪 Scripts de teste
│   ├── test_container_down_vs_up.sh
│   ├── test_container_detailed.sh
│   ├── test_alerts.sh
│   └── *.json
└── GRAFANA_METRICS_GUIDE.md  # 📚 Guia de configuração
```

## 🔍 Troubleshooting

### Problemas Comuns

#### 1. Alertas não chegam no Discord

```bash
# Verificar conectividade
curl -X POST $DISCORD_WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{"content":"Teste de conectividade"}'

# Verificar logs do proxy
docker-compose logs -f grafana-discord-proxy

# Testar endpoint manualmente
curl -X POST http://localhost:5001/alert \
  -H "Content-Type: application/json" \
  --data @test/test_alert_endpoint.json
```

#### 2. Containers não são detectados corretamente

```bash
# Habilitar debug
export DEBUG_MODE=true
docker-compose restart grafana-discord-proxy

# Testar com payload específico
./test/test_container_down_vs_up.sh

# Verificar logs de parsing
docker-compose logs grafana-discord-proxy | grep "DEBUG.*Container"
```

#### 3. Templates com erros no Grafana

Use os templates fornecidos em `/templates/` que são livres dos erros:

- ❌ `float64` não definido
- ❌ `regexReplaceAll` não definido  
- ❌ `atof` não disponível

✅ **Solução**: Templates minimalistas com processamento no proxy

### Debug Avançado

```bash
# Modo debug completo
echo "DEBUG_MODE=true" >> .env
docker-compose up -d

# Monitorar requests em tempo real
docker-compose logs -f grafana-discord-proxy | grep -E "POST|DEBUG"

# Testar parsing manual
curl -X POST http://localhost:5001/alert_minimal \
  -H "Content-Type: text/plain" \
  --data "CONTAINER_ALERT_START
alertname: ContainerDown
status: firing
container_name: test-container
value_A: 0
CONTAINER_ALERT_END"
```

## 🤝 Contribuições

Contribuições são muito bem-vindas! Este projeto está em desenvolvimento ativo e há várias áreas onde você pode ajudar:

### 🎯 Como Contribuir

1. **Fork** este repositório
2. **Crie** uma branch para sua feature (`git checkout -b feature/nova-funcionalidade`)
3. **Commit** suas mudanças (`git commit -am 'Adiciona nova funcionalidade'`)
4. **Push** para a branch (`git push origin feature/nova-funcionalidade`)
5. **Abra** um Pull Request

### 🛠️ Áreas que Precisam de Ajuda

- **🧪 Testes**: Mais cenários de teste para diferentes tipos de alerta
- **📊 Métricas**: Suporte a novos tipos de métricas e dashboards
- **🎨 Templates**: Templates adicionais para diferentes configurações
- **🔧 Integração**: Suporte a outras plataformas (Slack, Teams, etc.)
- **📚 Documentação**: Melhorias na documentação e exemplos
- **🚀 Performance**: Otimizações e melhorias de desempenho
- **🛡️ Segurança**: Validações adicionais e hardening

### 📋 Guidelines para PRs

- ✅ **Testes**: Inclua testes para novas funcionalidades
- ✅ **Documentação**: Atualize o README se necessário
- ✅ **Código**: Siga o padrão de código existente
- ✅ **Commits**: Use mensagens descritivas
- ✅ **Compatibilidade**: Mantenha compatibilidade com versões existentes

### 🐛 Reportando Bugs

Ao reportar bugs, inclua:

- **Versão** do proxy
- **Configuração** do Grafana
- **Logs** do container
- **Payload** que causou o problema
- **Comportamento esperado** vs **comportamento atual**

### 💡 Sugerindo Features

Para sugerir novas funcionalidades:

- **Descreva** o problema que a feature resolveria
- **Explique** como você imagina que funcionaria
- **Forneça** exemplos de uso
- **Considere** a compatibilidade com o código existente

---

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

---

Desenvolvido com ❤️ para melhorar a experiência de monitoramento e observabilidade.

🌟 Se este projeto te ajudou, considere dar uma estrela no GitHub!
