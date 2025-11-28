# Configuração Recomendada: PortainerMonitor + Grafana

## Seu Cenário

- ✅ **Alertas de Container (down/up)**: Controlados pelo **PortainerMonitor** (não pelo Grafana)
- ✅ **Alertas de Recursos (CPU/Memória/Disco)**: Recebidos do **Grafana**
- ✅ **Supressão**: Ativa para evitar spam de containers conhecidos (exit/restarting)
- ✅ **Whitelist**: Containers críticos sempre alertam

## Configuração no `.env`

```bash
# ===== PORTAINER - VALIDAÇÃO E MONITORAMENTO =====
CONTAINER_VALIDATE_WITH_PORTAINER=true
PORTAINER_BASE_URL=https://seu-portainer.com/api
PORTAINER_API_KEY=ptr_sua_chave_aqui
PORTAINER_ENDPOINT_MAP_FILE=config/portainer_endpoints.json

# ===== MONITORAMENTO ATIVO =====
# Habilita detecção ativa de containers down
PORTAINER_ACTIVE_MONITOR=true
PORTAINER_MONITOR_INTERVAL_SECONDS=30

# 🔑 PortainerMonitor é a ÚNICA fonte de alertas de container
# Ignora alertas de container do Grafana (mas aceita CPU/Mem/Disk)
PORTAINER_MONITOR_ONLY_SOURCE=true

# ===== SUPRESSÃO DE CONTAINERS =====
# Habilita supressão (evita spam de containers conhecidos)
CONTAINER_SUPPRESS_REPEATS=true
CONTAINER_SUPPRESS_TTL_SECONDS=86400  # 24 horas

# Persistência (mantém estado após restart)
CONTAINER_SUPPRESS_PERSIST=true
CONTAINER_SUPPRESS_STATE_FILE=/tmp/proxy-alertmanager-suppression-state.json

# ===== WHITELISTS =====
# Containers que SEMPRE geram alerta (ignoram supressão)
CONTAINER_ALWAYS_NOTIFY_ALLOWLIST=api-prod,database,nginx-prod,worker-critical

# Containers completamente IGNORADOS (sem alertas)
CONTAINER_IGNORE_ALLOWLIST=test-container,dev-sandbox,tmp-worker

# Containers que podem ficar em "paused" sem alertar
CONTAINER_PAUSED_ALLOWLIST=batch-job,scheduled-task

# ===== SUPRESSÃO BLUE/GREEN =====
# Suprime alertas quando o par (blue/green) está ativo
BLUE_GREEN_SUPPRESSION_ENABLED=true

# ===== DEDUPE =====
# Evita alertas duplicados dentro de 30 minutos
ALERT_DEDUP_ENABLED=true
ALERT_COOLDOWN_SECONDS=1800
```

## Como Funciona

### 1. Alertas de Container (PortainerMonitor)

```
PortainerMonitor detecta:
  → Container down
  → Verifica supressão
  → Verifica whitelist
  → Envia para Discord ✅

Grafana envia alerta de container:
  → Proxy recebe
  → Verifica PORTAINER_MONITOR_ONLY_SOURCE=true
  → IGNORA alerta ❌
```

### 2. Alertas de Recursos (Grafana)

```
Grafana envia alerta de CPU/Memória/Disco:
  → Proxy recebe
  → Tipo detectado: cpu/memory/disk
  → Formata e envia para Discord ✅
```

### 3. Supressão

```
Container "archive" down:
  → Primeira vez → Alerta enviado ✅
  → Ainda down → Suprimido 🚫
  → Ainda down → Suprimido 🚫
  → Volta running → Reset
  → Down novamente → Alerta enviado ✅

Container "api-prod" down (no whitelist):
  → Primeira vez → Alerta enviado ✅
  → Ainda down → Alerta enviado ✅ (whitelist ignora supressão)
  → Ainda down → Alerta enviado ✅

Container "test-container" down (ignorado):
  → Nunca envia alerta ❌
```

## Fluxo de Trabalho

### Cenário 1: Container Crítico Cai

```
1. PortainerMonitor detecta "api-prod" down
2. Verifica whitelist → "api-prod" está em CONTAINER_ALWAYS_NOTIFY_ALLOWLIST
3. Ignora supressão
4. Envia alerta para Discord ✅
5. A cada 30 segundos, continua enviando (dedupe pode limitar frequência)
```

### Cenário 2: Container de Teste Cai

```
1. PortainerMonitor detecta "test-container" down
2. Verifica whitelist → "test-container" está em CONTAINER_IGNORE_ALLOWLIST
3. Não envia alerta ❌
```

### Cenário 3: Container Normal Cai

```
1. PortainerMonitor detecta "archive" down
2. Verifica supressão → Primeira falha
3. Envia alerta para Discord ✅
4. Marca como suprimido
5. Próximas detecções → Suprimido 🚫
6. Container volta a running → Reset
7. Cai novamente → Envia novo alerta ✅
```

### Cenário 4: Container com Blue/Green

```
1. PortainerMonitor detecta "app-blue" down
2. Verifica se "app-green" está running
3. "app-green" está running → Suprime alerta 🚫 (deployment normal)
4. Se ambos caírem → Envia alertas ✅
```

## Vantagens desta Configuração

| Benefício | Descrição |
|-----------|-----------|
| ✅ **Sem Duplicatas** | PortainerMonitor é a única fonte de alertas de container |
| ✅ **Controle Total** | Você decide quais containers alertam via whitelist |
| ✅ **Menos Spam** | Supressão evita alertas repetidos de containers conhecidos |
| ✅ **Recursos Separados** | CPU/Memória/Disco continuam vindo do Grafana |
| ✅ **Persistência** | Estado mantido após restart (sem spam) |
| ✅ **Blue/Green** | Suporta deployments sem falsos alertas |

## Testando a Configuração

### 1. Testar Container Crítico

```bash
# Pare um container no whitelist
docker stop api-prod

# Deve enviar alerta em até 30 segundos
```

### 2. Testar Container Ignorado

```bash
# Pare um container ignorado
docker stop test-container

# NÃO deve enviar alerta
```

### 3. Testar Supressão

```bash
# Pare um container normal
docker stop archive

# Alerta enviado ✅

# Aguarde 30 segundos - NÃO deve enviar novo alerta 🚫

# Inicie o container
docker start archive

# Aguarde 30 segundos - NÃO deve enviar alerta 🚫

# Pare novamente
docker stop archive

# Deve enviar novo alerta ✅
```

### 4. Testar Grafana (CPU/Memória)

Alertas de CPU/Memória/Disco do Grafana devem continuar funcionando normalmente.

## Logs de Debug

Com `DEBUG_MODE=true`, você verá:

```
[DEBUG] PortainerMonitor: queda detectada - endpoint=20 container=archive
[DEBUG] PortainerMonitor: suppression check key=159.65.46.83|id:abc123 state=down send=True reason=first_failure_since_running
[DEBUG] PortainerMonitor: enviando alerta para Discord

[DEBUG] Alerta de container 'test-container' do Grafana IGNORADO (PORTAINER_MONITOR_ONLY_SOURCE=true)

[DEBUG] PortainerMonitor: alerta suprimido (reason=already_suppressed_until_running)
```

## Troubleshooting

### Problema: Container no whitelist ainda é suprimido

Verifique se o nome está exatamente como no Portainer (case-sensitive):

```bash
# Liste os containers para ver o nome exato
docker ps -a --format "{{.Names}}"

# Adicione ao whitelist com o nome exato
CONTAINER_ALWAYS_NOTIFY_ALLOWLIST=api-prod,database
```

### Problema: Muitos alertas repetidos

Ajuste o dedupe:

```bash
ALERT_COOLDOWN_SECONDS=3600  # 1 hora entre alertas iguais
```

Ou aumente o intervalo:

```bash
PORTAINER_MONITOR_INTERVAL_SECONDS=60  # Verifica a cada 1 minuto
```

### Problema: Não recebe alertas de container

Verifique:

```bash
# 1. PortainerMonitor está habilitado?
PORTAINER_ACTIVE_MONITOR=true

# 2. ONLY_SOURCE está habilitado?
PORTAINER_MONITOR_ONLY_SOURCE=true

# 3. Container não está na ignore list?
# Remova da CONTAINER_IGNORE_ALLOWLIST se necessário
```
