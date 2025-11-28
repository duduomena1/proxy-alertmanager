# PortainerMonitor como Única Fonte de Alertas de Container

## Problema

Por padrão, o sistema recebe alertas de container tanto do Grafana quanto pode detectá-los via PortainerMonitor. Isso pode causar:
- Alertas duplicados
- Conflito entre as duas fontes
- Falta de controle sobre qual fonte usar

## Solução

Use `PORTAINER_MONITOR_ONLY_SOURCE=true` para:
- **Alertas de Container (down/up)**: Controlados **APENAS pelo PortainerMonitor**
- **Alertas de Recursos (CPU/Memória/Disco)**: Continuam vindo do **Grafana normalmente**
- **Supressão**: Funciona normalmente, respeitando o whitelist

## Configuração

### Passo 1: Habilitar Monitoramento Ativo

```bash
# Habilita o PortainerMonitor (polling ativo)
PORTAINER_ACTIVE_MONITOR=true

# Intervalo de verificação (em segundos)
PORTAINER_MONITOR_INTERVAL_SECONDS=30

# Habilita Portainer
CONTAINER_VALIDATE_WITH_PORTAINER=true
PORTAINER_BASE_URL=https://seu-portainer.com/api
PORTAINER_API_KEY=ptr_sua_chave_aqui
```

### Passo 2: Configurar PortainerMonitor como Única Fonte

```bash
# 🔑 CHAVE: PortainerMonitor é a única fonte de alertas de container
# Alertas de container do Grafana serão IGNORADOS
PORTAINER_MONITOR_ONLY_SOURCE=true
```

### Passo 3: Configurar Whitelist (Recomendado)

Para containers que você **sempre quer ser alertado** (ignoram supressão):

```bash
# Containers críticos que sempre geram alerta
CONTAINER_ALWAYS_NOTIFY_ALLOWLIST=api-prod,database,nginx-prod
```

Para containers que você **NÃO quer alertas** (ex: containers de teste que ficam em exit):

```bash
# Containers ignorados completamente
CONTAINER_IGNORE_ALLOWLIST=test-container,tmp-worker,dev-sandbox
```

## Comportamento

### Com `PORTAINER_MONITOR_ALWAYS_ALERT=false` (padrão)

```
Container down → Alerta enviado ✅
Container ainda down → Alerta suprimido 🚫
Container ainda down → Alerta suprimido 🚫
Container running → Reset
Container down → Alerta enviado ✅
```

**Problema**: Se você restart a aplicação, os alertas podem ser suprimidos mesmo que os containers estejam down.

### Com `PORTAINER_MONITOR_ALWAYS_ALERT=true` 

```
Container down → Alerta enviado ✅
Container ainda down (30s depois) → Alerta enviado ✅
Container ainda down (60s depois) → Alerta enviado ✅
[RESTART DA APLICAÇÃO]
Container ainda down → Alerta enviado ✅
```

**Benefício**: Você recebe alertas toda vez que o monitor detecta containers down, independente do histórico.

## Configuração Completa Recomendada

Para usar **APENAS o PortainerMonitor** sem Grafana:

```bash
# ===== PORTAINER =====
CONTAINER_VALIDATE_WITH_PORTAINER=true
PORTAINER_BASE_URL=https://seu-portainer.com/api
PORTAINER_API_KEY=ptr_sua_chave_aqui
PORTAINER_ENDPOINT_MAP_FILE=config/portainer_endpoints.json

# ===== MONITORAMENTO ATIVO =====
PORTAINER_ACTIVE_MONITOR=true
PORTAINER_MONITOR_INTERVAL_SECONDS=30
PORTAINER_MONITOR_ALWAYS_ALERT=true

# ===== SUPRESSÃO (Opcional) =====
# Você pode desabilitar totalmente a supressão se quiser alertas toda vez
CONTAINER_SUPPRESS_REPEATS=false
CONTAINER_SUPPRESS_PERSIST=false

# Ou manter a supressão mas adicionar containers críticos ao allowlist
CONTAINER_ALWAYS_NOTIFY_ALLOWLIST=api-prod,database,nginx
```

## Controle de Frequência

Com `PORTAINER_MONITOR_ALWAYS_ALERT=true`, você ainda pode controlar a frequência dos alertas usando:

### 1. Dedupe (Recomendado)

```bash
ALERT_DEDUP_ENABLED=true
ALERT_COOLDOWN_SECONDS=1800  # 30 minutos entre alertas do mesmo container
```

### 2. Intervalo do Monitor

```bash
PORTAINER_MONITOR_INTERVAL_SECONDS=60  # Verifica a cada 60 segundos
```

### 3. Confirmações Necessárias

```bash
PORTAINER_MONITOR_DOWN_CONFIRMATIONS=2  # Requer 2 verificações consecutivas antes de alertar
```

## Comparação: Grafana vs PortainerMonitor

| Característica | Grafana + Proxy | PortainerMonitor Only |
|----------------|-----------------|----------------------|
| **Fonte dos Alertas** | Prometheus → Grafana → Proxy | Portainer → Proxy |
| **Detecção** | Baseada em métricas | Baseada em estado do container |
| **Latência** | Depende do scrape interval | Tempo real (polling) |
| **Configuração** | Mais complexa (Prometheus + regras) | Simples (variáveis de ambiente) |
| **Alertas de Métricas** | ✅ CPU, Memória, Disco, Containers | ❌ Apenas containers |
| **Dependências** | Prometheus, Grafana | Apenas Portainer |
| **Recomendado para** | Monitoramento completo | Apenas status de containers |

## Exemplo de Log

Com `PORTAINER_MONITOR_ALWAYS_ALERT=true` e `DEBUG_MODE=true`:

```
[DEBUG] PortainerMonitor: queda detectada - endpoint=20 container=archive
[DEBUG] PortainerMonitor: ALWAYS_ALERT ativado - ignorando supressão para archive
[DEBUG] PortainerMonitor: enviando alerta para Discord
✅ Alerta enviado para Discord
```

## Quando Usar

### Use `PORTAINER_MONITOR_ALWAYS_ALERT=true` quando:

- ✅ Você quer usar **apenas o PortainerMonitor** sem Grafana
- ✅ Você quer alertas **toda vez** que verificar e encontrar containers down
- ✅ Você prefere receber mais alertas do que perder algum
- ✅ Você tem controle de frequência via dedupe ou intervalo longo

### Use `PORTAINER_MONITOR_ALWAYS_ALERT=false` (padrão) quando:

- ✅ Você usa **Grafana + PortainerMonitor** juntos
- ✅ Você quer alertas **apenas na primeira vez** que um container cai
- ✅ Você prefere menos alertas (mais silencioso)
- ✅ Você quer que a supressão funcione normalmente

## Troubleshooting

### "Alerta suprimido" mesmo com ALWAYS_ALERT=true

Verifique se a variável está corretamente configurada:

```bash
# No .env
PORTAINER_MONITOR_ALWAYS_ALERT=true

# Restart da aplicação
docker-compose restart proxy-alertmanager
```

### Muitos alertas repetidos

Configure o dedupe:

```bash
ALERT_DEDUP_ENABLED=true
ALERT_COOLDOWN_SECONDS=3600  # 1 hora
```

Ou aumente o intervalo:

```bash
PORTAINER_MONITOR_INTERVAL_SECONDS=120  # 2 minutos
```

### Container flapping (up/down/up/down)

Use confirmações:

```bash
PORTAINER_MONITOR_DOWN_CONFIRMATIONS=3  # Requer 3 verificações consecutivas
```
