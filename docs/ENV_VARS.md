# 📖 Referência de Variáveis de Ambiente

Este documento lista todas as variáveis de ambiente suportadas pelo projeto, seus valores padrão e exemplos práticos de configuração.

> Dica: para desenvolvimento, use o arquivo `.env` (baseado em `.env.example`). Em produção (Docker/K8s), defina-as em `environment:` ou via Secrets/ConfigMaps.

## 🔗 Básico

- DISCORD_WEBHOOK_URL (obrigatório)
  - URL do webhook do Discord para envio das mensagens.
  - Ex.: <https://discord.com/api/webhooks/XXX/YYY>
- APP_PORT (default: 5001)
  - Porta HTTP do proxy.
- DEBUG_MODE (default: false)
  - Ativa logs detalhados.

## 🔁 Dedupe/Cooldown de Alertas

- ALERT_DEDUP_ENABLED (default: true)
  - Habilita desduplicação temporal de payloads idênticos.
- ALERT_COOLDOWN_SECONDS (default: 3600)
  - Janela de tempo (em segundos) para considerar um alerta como duplicado.
- ALERT_CACHE_MAX (default: 5000)
  - Tamanho máximo do cache de fingerprints.

## 🐳 Supressão de Containers por Estado

- CONTAINER_SUPPRESS_REPEATS (default: true)
  - Habilita a máquina de estados que evita reenvio enquanto o container não voltar a `running`.
- CONTAINER_SUPPRESS_TTL_SECONDS (default: 86400)
  - TTL do estado. Após esse tempo sem eventos, o estado é limpo.
- **CONTAINER_SUPPRESS_PERSIST** (default: true) 🆕
  - Habilita persistência do estado de supressão em arquivo JSON.
  - **Benefício**: Ao fazer rebuild/restart da aplicação, não reenvia alertas de containers já conhecidos como down.
- **CONTAINER_SUPPRESS_STATE_FILE** (default: /tmp/proxy-alertmanager-suppression-state.json) 🆕
  - Caminho do arquivo onde o estado de supressão é salvo.
  - **Recomendação**: Em produção, use um volume persistente (ex: `/var/lib/proxy-alertmanager/suppression-state.json`).
- CONTAINER_PAUSED_ALLOWLIST (default: "")
  - Lista separada por vírgula com nomes/IDs de containers que podem ficar `paused` sem alertar, e sem ativar supressão.
  - Ex.: CONTAINER_PAUSED_ALLOWLIST=nginx_paused,batch-worker
- CONTAINER_ALWAYS_NOTIFY_ALLOWLIST (default: "")
  - Lista separada por vírgula com nomes/IDs de containers que NUNCA devem ser suprimidos: sempre enviar alerta, mesmo que repetido ou dentro do cooldown de dedupe.
  - Ex.: CONTAINER_ALWAYS_NOTIFY_ALLOWLIST=api-prod,worker-1,nginx-edge
- CONTAINER_IGNORE_ALLOWLIST (default: "")
  - Lista separada por vírgula com nomes/IDs de containers que devem ser completamente ignorados (sem alertas em nenhum estado).
  - Ex.: CONTAINER_IGNORE_ALLOWLIST=test-container,tmp-worker

Comportamento:

- Primeira falha (down/restarting/exited/...) → envia alerta e ativa supressão.
- Próximas falhas com o mesmo estado (sem ter passado por `running`) → suprimidas.
- Quando o container voltar a `running` → supressão é resetada; um novo down voltará a alertar.
- **Com persistência habilitada**: Estado sobrevive ao restart da aplicação → sem spam de alertas após rebuild! 🎉

### Supressão Blue/Green Deployment

- BLUE_GREEN_SUPPRESSION_ENABLED (default: true)
  - Habilita supressão inteligente para deployments blue/green: se um container cai (ex: `app-blue`) mas seu par (ex: `app-green`) está rodando no mesmo endpoint, o alerta é suprimido.
  - Suporta padrões de nomenclatura: `app-blue`/`app-green`, `app_blue`/`app_green` (case-insensitive).
  - Se ambos os containers do par caírem, os alertas são enviados normalmente.
  - Requer `CONTAINER_VALIDATE_WITH_PORTAINER=true` para funcionar.

Exemplos de containers detectados:

- `nginx-blue` ↔ `nginx-green`
- `api_blue` ↔ `api_green`
- `WORKER-BLUE` ↔ `WORKER-GREEN` (case-insensitive)

## 🔁 Integração com Portainer

- CONTAINER_VALIDATE_WITH_PORTAINER (default: false)
  - Valida o estado do container via API do Portainer ao processar alertas do Grafana.
- PORTAINER_BASE_URL (ex.: <https://portainer.local/api>)
- PORTAINER_API_KEY (chave de API criada no Portainer)
- PORTAINER_TIMEOUT_SECONDS (default: 3)
- PORTAINER_VERIFY_TLS (default: true)
- PORTAINER_FAIL_OPEN (default: true)
  - Se true, falhas na API não bloqueiam o fluxo (prossegue com melhor esforço).
- PORTAINER_ENDPOINT_MAP_FILE (ex.: config/portainer_endpoints.json)
  - Mapa nome→endpointId ou IP→endpointId usado para resolver hosts.
- PORTAINER_STRICT_NAME_MATCH (default: false)
  - Se true, exige match de nome exato do container.

### Monitoramento Ativo (PortainerMonitor)

- PORTAINER_ACTIVE_MONITOR (default: false)
  - Liga o poller ativo que detecta quedas diretamente no Portainer.
- PORTAINER_MONITOR_INTERVAL_SECONDS (default: 30)
- PORTAINER_MONITOR_ENDPOINTS (default: "")
  - Filtro opcional (lista separada por vírgula) de endpoints por ID ou nome.
- PORTAINER_MONITOR_DOWN_CONFIRMATIONS (default: 1)
  - Número de ciclos consecutivos não-running para confirmar a queda.
- PORTAINER_MONITOR_SCOPE (default: map)
  - 'map' para restringir aos endpoints do arquivo de mapa; 'all' para monitorar todos.

Observação: o monitor ativo também respeita a supressão por estado e o allowlist de `paused`.

## 🎨 Aparência (cores e GIFs)

Cores são decimais (equivalente ao RGB em decimal). Todas são opcionais.

- CONTAINER_DOWN_COLOR (default: 16711680)
- CONTAINER_DOWN_GIF (url)
- CONTAINER_UP_COLOR (default: 65280)
- CONTAINER_UP_GIF (url)

Severidades genéricas (CPU/Mem/Disk/Default):

- CPU_LOW_COLOR, CPU_MEDIUM_COLOR, CPU_HIGH_COLOR
- MEMORY_LOW_COLOR, MEMORY_MEDIUM_COLOR, MEMORY_HIGH_COLOR
- DISK_LOW_COLOR, DISK_MEDIUM_COLOR, DISK_HIGH_COLOR
- DEFAULT_LOW_COLOR, DEFAULT_MEDIUM_COLOR, DEFAULT_HIGH_COLOR
- GIFs equivalentes: CPU_LOW_GIF, MEMORY_MEDIUM_GIF, DISK_HIGH_GIF, etc.

## 📦 Exemplo de .env (trecho)

```env
# Básico
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/XXX/YYY
APP_PORT=5001
DEBUG_MODE=true

# Supressão por estado
CONTAINER_SUPPRESS_REPEATS=true
CONTAINER_SUPPRESS_TTL_SECONDS=86400
CONTAINER_PAUSED_ALLOWLIST=nginx_paused,batch-worker
CONTAINER_ALWAYS_NOTIFY_ALLOWLIST=api-prod,worker-1,nginx-edge
BLUE_GREEN_SUPPRESSION_ENABLED=true

# Portainer
CONTAINER_VALIDATE_WITH_PORTAINER=true
PORTAINER_BASE_URL=https://portainer.local/api
PORTAINER_API_KEY=xxxxxxxxxxxxxxxx
PORTAINER_ENDPOINT_MAP_FILE=config/portainer_endpoints.json
PORTAINER_ACTIVE_MONITOR=true
PORTAINER_MONITOR_INTERVAL_SECONDS=30
PORTAINER_MONITOR_SCOPE=map

# Aparência (opcional)
CONTAINER_DOWN_COLOR=16711680
CONTAINER_UP_COLOR=65280
```
