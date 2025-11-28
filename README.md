# 🚀 Grafana Discord Proxy

Sistema de monitoramento que integra Grafana, Prometheus e Portainer para enviar alertas formatados ao Discord.

## ✨ Características

- 🔍 **Monitoramento Ativo via Portainer**: Detecta containers DOWN/UP em tempo real (30s)
- 📊 **Alertas do Grafana**: CPU, Memória, Disco formatados
- 🛡️ **Supressão Inteligente**: Evita spam com persistência entre restarts
- 🔄 **Blue/Green Deployment**: Supressão automática quando sibling está ativo
- 💾 **Persistência**: Estado mantido em volume Docker

## 🎯 Arquitetura

```
┌─────────────┐
│   Grafana   │ → Alertas de CPU/Memória/Disco (webhook /alert)
└─────────────┘   📍 Apenas formatação, NÃO verifica containers
       ↓
┌─────────────┐
│  Portainer  │ → Monitor ativo de containers (polling 30s)
└─────────────┘   🔍 Detecção UP/DOWN, 🛡️ Supressão inteligente
       ↓
┌─────────────┐
│   Discord   │ ← Todas as notificações
└─────────────┘
```

**Separação de Responsabilidades:**
- **Grafana**: Envia alertas de métricas → Proxy APENAS formata
- **Portainer**: Monitor ativo de containers → Proxy detecta e alerta DOWN/UP

## 🚀 Quick Start

```bash
# 1. Clone e configure
git clone <seu-repo>
cd proxy-alertmanager
cp .env.example .env

# 2. Edite o .env com suas credenciais
nano .env

# 3. Suba o container
docker-compose up -d

# 4. Verifique logs
docker logs grafana-discord-proxy-prod -f
```

## 📋 Variáveis Principais

```bash
# Discord (obrigatório)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Portainer (obrigatório)
PORTAINER_BASE_URL=http://portainer:9000
PORTAINER_API_KEY=ptr_xxx...

# Monitoramento Ativo (recomendado)
PORTAINER_ACTIVE_MONITOR=true
PORTAINER_MONITOR_ONLY_SOURCE=true
PORTAINER_MONITOR_INTERVAL_SECONDS=30

# Supressão (padrão: habilitado)
CONTAINER_SUPPRESS_REPEATS=true
CONTAINER_SUPPRESS_TTL_SECONDS=86400  # 24h
CONTAINER_SUPPRESS_PERSIST=true

# Blue/Green
BLUE_GREEN_SUPPRESSION_ENABLED=true

# Debug
DEBUG_MODE=false
```

## 🔧 Endpoints

- **GET** `/health` - Health check
- **POST** `/alert` - Alertas do Grafana (formato JSON padrão)
- **POST** `/alert_minimal` - Alertas do Grafana (formato minimal template)

## 📖 Configuração Grafana

### Contact Point

```yaml
Name: Discord via Proxy
Type: Webhook
URL: http://seu-proxy:5001/alert
Method: POST
```

### Mapeamento Portainer

Crie `config/portainer_endpoints.json`:

```json
{
  "192.168.1.10": 1,
  "192.168.1.20": 2,
  "server-prod": 3
}
```

Onde a chave é o `instance` do Prometheus e o valor é o `endpoint_id` do Portainer.

## 🐳 Rebuild Rápido

```bash
./rebuild.sh
```

## 🛠️ Como Funciona

### Monitoramento de Containers

1. **Portainer Monitor** (thread separada):
   - Polling a cada 30s em todos os endpoints configurados
   - Detecta transições DOWN→UP e UP→DOWN
   - Aplica supressão para evitar spam
   - Verifica blue/green siblings antes de alertar

2. **Supressão de Alertas**:
   - **Estados problemáticos**: `down`, `restarting`, `exited`, `dead`, `unknown`
   - **Primeira falha**: Envia alerta e ativa supressão
   - **Falhas subsequentes**: Suprimido até voltar a `running`
   - **Recuperação**: Reset da supressão quando volta a `running`
   - **Persistência**: Estado salvo em `/app/data/suppression-state.json`

3. **Blue/Green Deployment**:
   - Detecta padrão `app-blue`, `app-green`
   - Se `app-blue` cai mas `app-green` está UP → Suprime alerta
   - Se ambos caem → Alerta normalmente

### Alertas do Grafana

- **CPU/Memória/Disco**: Recebe via webhook, formata e envia ao Discord
- **Container**: Ignorado (Portainer é a fonte única)

## 📊 Exemplo de Alerta

```
🚨 CONTAINER OFFLINE

📊 Detalhes Técnicos
Alert: ContainerDown - nginx-prod
Severidade: CONTAINER OFFLINE

🔁 Portainer
🔴 Estado: exited
📛 Nome: nginx-prod

📍 Localização
🖥️ Servidor: 192.168.1.10
⏰ Timestamp: 2025-11-28 14:32:10
```

## 📚 Documentação Completa

- [Variáveis de Ambiente](docs/ENV_VARS.md) - Todas as configurações
- [Integração Portainer](docs/PORTAINER_INTEGRATION.md) - Setup detalhado
- [Separação de Responsabilidades](docs/PORTAINER_MONITOR_SEPARATION.md) - Arquitetura
- [Supressão de Alertas](docs/CONTAINER_SUPPRESSION.md) - Regras e lógica
- [Persistência de Estado](docs/SUPPRESSION_PERSISTENCE.md) - Como funciona

## 🐛 Troubleshooting

### Alertas duplicados no rebuild

**Problema**: Ao rebuildar container, recebe todos os alertas novamente.

**Solução**: ✅ Implementada persistência de estado em volume Docker (`./data`). O estado de supressão é mantido entre restarts.

### Containers mostrando apenas ID

**Problema**: Alguns alertas mostram `container-abc123` ao invés do nome.

**Solução**: ✅ Implementado fallback em múltiplas etapas:
1. `Names[0]`
2. `Name`
3. `Labels['com.docker.compose.service']`
4. `container-{ID[:12]}`

### Alertas de container quando faz deploy blue/green

**Problema**: Recebe alerta de DOWN quando troca `app-blue` por `app-green`.

**Solução**: ✅ Blue/green suppression habilitado por padrão. Se sibling estiver UP, alerta é suprimido.

### Debug

```bash
# Habilitar logs detalhados
docker-compose down
# Edite .env: DEBUG_MODE=true
docker-compose up -d
docker logs grafana-discord-proxy-prod -f
```

## 📝 Changelog

**v2.0.0** - 28/11/2025
- ✅ Separação: Portainer monitora containers, Grafana monitora métricas
- ✅ Persistência de estado de supressão em volume
- ✅ Deduplicação de containers por ID
- ✅ Melhorias na extração de nomes
- ✅ Suporte blue/green deployment
- ✅ Fix: Alertas duplicados no rebuild

## 📄 Licença

MIT
