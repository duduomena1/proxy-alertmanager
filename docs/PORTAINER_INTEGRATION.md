# 🔁 Integração com Portainer

Este guia explica como habilitar a validação de containers via Portainer e o monitoramento ativo de quedas.

## 🧰 Pré-requisitos

- Portainer acessível via API (URL e API Key)
- Mapa de endpoints (opcional, recomendado) em `config/portainer_endpoints.json`

Exemplo de `config/portainer_endpoints.json`:

```json
{
  "192.168.1.100": 15,
  "worker-node-01": 15,
  "db-node": 16
}
```

## ✅ Validação de estado no fluxo do Grafana

Ative a consulta ao Portainer durante o processamento de alertas de container:

```env
CONTAINER_VALIDATE_WITH_PORTAINER=true
PORTAINER_BASE_URL=https://portainer.local/api
PORTAINER_API_KEY=xxxxxxxxxxxxxxxx
PORTAINER_ENDPOINT_MAP_FILE=config/portainer_endpoints.json
PORTAINER_TIMEOUT_SECONDS=3
PORTAINER_VERIFY_TLS=true
PORTAINER_FAIL_OPEN=true
PORTAINER_STRICT_NAME_MATCH=false
```

Com isso, o proxy usa o estado real do container (running/paused/exited/...) para enriquecer a mensagem e melhorar as decisões (como a supressão por estado).

## 📡 Monitoramento ativo (PortainerMonitor)

O monitor percorre periodicamente os endpoints e detecta quedas mesmo sem alerta do Grafana.

Habilitar:

```env
PORTAINER_ACTIVE_MONITOR=true
PORTAINER_MONITOR_INTERVAL_SECONDS=30
PORTAINER_MONITOR_SCOPE=map  # ou 'all'
# Filtrar endpoints por ID ou nome (opcional)
PORTAINER_MONITOR_ENDPOINTS=15,db-node
# Histerese para confirmar queda
PORTAINER_MONITOR_DOWN_CONFIRMATIONS=1
```

Notas importantes:

- O monitor também usa a supressão por estado: após a 1ª queda, não reenvia até observar `running` novamente.
- `paused` é tratado especialmente; combine com `CONTAINER_PAUSED_ALLOWLIST` quando necessário.

## 🧪 Verificação e logs (DEBUG_MODE=true)

- Inicialização do monitor:
  - `[DEBUG] PortainerMonitor iniciado (intervalo=30s)`
- Snapshot e confirmações:
  - `[DEBUG] PortainerMonitor: queda detectada - endpoint=15 container=nginx` (quando confirmado)
- Supressão:
  - `[DEBUG] PortainerMonitor: suppression check key=... state=... send=... reason=...`

Se observar dedupe suprimindo alertas periódicos, mas sem `running` no meio, a supressão por estado cuidará para não re-alertar até que o container se recupere.
