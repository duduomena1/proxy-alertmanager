# Separação de Responsabilidades: Grafana vs Portainer

## Mudança Implementada - 28/11/2025

### Problema Anterior

Quando um container caía, o sistema ficava aguardando o alerta do Grafana/Prometheus para poder enviar a notificação. Isso causava atrasos significativos, pois:

1. O Prometheus pode demorar para detectar que o container está DOWN
2. O Grafana precisa avaliar as regras de alerta
3. O webhook só é enviado depois de todo esse processamento
4. **Resultado**: Container pode ficar DOWN por minutos sem notificação

### Solução Implementada

Separamos as responsabilidades de forma clara:

#### 1. **Portainer = Monitor de Containers (UP/DOWN)**

- O `PortainerMonitor` agora é a **fonte exclusiva** de alertas de container
- Monitora ativamente os containers em intervalos configuráveis (padrão: 30 segundos)
- Detecta imediatamente quando um container:
  - **CAI** (DOWN): Estado muda de `running` para `stopped`, `exited`, `paused`, etc.
  - **VOLTA** (UP): Estado muda de `stopped`/`exited` para `running`
- Envia notificações instantâneas para o Discord

#### 2. **Grafana = Formatação de Alertas (CPU, Memória, Disco)**

- Alertas do Grafana agora **apenas formatam** as informações recebidas
- Não consultam mais o Portainer para verificar estado de containers
- Focam em métricas de sistema:
  - CPU
  - Memória
  - Disco
  - Outros alertas customizados

### Configurações Alteradas

#### No arquivo `app/constants.py`:

```python
# ANTES:
PORTAINER_ACTIVE_MONITOR = os.getenv("PORTAINER_ACTIVE_MONITOR", "false").lower() == "true"
PORTAINER_MONITOR_ONLY_SOURCE = os.getenv("PORTAINER_MONITOR_ONLY_SOURCE", "false").lower() == "true"

# DEPOIS:
PORTAINER_ACTIVE_MONITOR = os.getenv("PORTAINER_ACTIVE_MONITOR", "true").lower() == "true"
PORTAINER_MONITOR_ONLY_SOURCE = os.getenv("PORTAINER_MONITOR_ONLY_SOURCE", "true").lower() == "true"
```

**Resultado**: Por padrão, o Portainer agora monitora ativamente os containers e ignora alertas de container vindos do Grafana.

### Vantagens

1. **Detecção Instantânea**: Containers DOWN são detectados em até 30 segundos (configurável)
2. **Monitoramento de Recuperação**: Notifica quando containers voltam a funcionar
3. **Separação Clara**: Grafana cuida de métricas de sistema, Portainer cuida de containers
4. **Menos Dependência**: Não depende mais do Prometheus/Grafana para alertas de container
5. **Menos Carga**: Grafana não precisa mais consultar o Portainer

### Configurações Disponíveis

#### Variáveis de Ambiente no `.env`:

```bash
# Ativa o monitoramento ativo via Portainer (padrão: true)
PORTAINER_ACTIVE_MONITOR=true

# Portainer como fonte exclusiva de alertas de container (padrão: true)
PORTAINER_MONITOR_ONLY_SOURCE=true

# Intervalo de verificação em segundos (padrão: 30)
PORTAINER_MONITOR_INTERVAL_SECONDS=30

# Confirmações necessárias antes de alertar DOWN (padrão: 2)
PORTAINER_MONITOR_DOWN_CONFIRMATIONS=2

# Endpoints a monitorar (vazio = usa mapa de config/portainer_endpoints.json)
PORTAINER_MONITOR_ENDPOINTS=

# Escopo de monitoramento: 'all' ou 'map' (padrão: map)
PORTAINER_MONITOR_SCOPE=map
```

### Comportamento dos Alertas

#### Alertas de Container (Portainer):
- ✅ **DOWN detectado**: Envia notificação vermelha 🔴 com estado do container
- ✅ **UP detectado**: Envia notificação verde 🟢 confirmando recuperação
- ✅ **Supressão inteligente**: Evita spam de alertas repetidos
- ✅ **Blue/Green awareness**: Respeita ambientes blue/green

#### Alertas do Grafana (CPU/Memória/Disco):
- 📊 **Formata as informações** recebidas do Grafana
- 🎨 **Aplica cores e GIFs** baseado na severidade
- 📍 **Enriquece com IP e localização** do servidor
- ⚡ **Não consulta Portainer** (mais rápido e eficiente)

### Compatibilidade

Se você quiser **desativar** o monitoramento ativo do Portainer e voltar ao comportamento anterior:

```bash
# No arquivo .env
PORTAINER_ACTIVE_MONITOR=false
PORTAINER_MONITOR_ONLY_SOURCE=false
```

Isso fará com que o sistema volte a depender apenas dos alertas do Grafana para containers.

### Testes Recomendados

1. **Teste de Container DOWN**:
   ```bash
   docker stop <container-name>
   ```
   - Você deve receber uma notificação em até 60 segundos (2 × intervalo padrão)

2. **Teste de Container UP**:
   ```bash
   docker start <container-name>
   ```
   - Você deve receber uma notificação confirmando que o container voltou

3. **Teste de Alertas do Grafana**:
   - Alertas de CPU/Memória/Disco devem continuar funcionando normalmente
   - Eles não tentarão mais consultar o Portainer

### Logs de Debug

Para acompanhar o funcionamento:

```bash
# Ver logs do container
docker logs grafana-discord-proxy-prod -f

# Procurar por:
# - "[DEBUG] PortainerMonitor: queda detectada"
# - "[DEBUG] PortainerMonitor: recuperação detectada"
# - "[DEBUG] Alerta de container 'X' do Grafana IGNORADO"
```
