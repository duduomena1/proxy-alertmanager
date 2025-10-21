# 🐳 Supressão de Alertas de Container por Estado

Este guia explica como o proxy evita alertas repetidos de containers que ficam falhando (ex.: restarting loop) até que voltem a `running`.

## 🔎 O que resolve?

Sem supressão, o mesmo container em `restarting` poderia gerar alertas indefinidamente (ou após expirar o cooldown do dedupe). A supressão por estado “trava” o alerta: só o primeiro é enviado e os seguintes são bloqueados até observarmos `running` novamente.

## ⚙️ Máquina de Estados (resumo)

- Estados problemáticos: `down`, `restarting`, `exited`, `dead`, `created`, `stopped`, `unknown`.
- Estado saudável: `running`.
- Estado especial: `paused`.

Regras:

- 1ª transição para estado problemático → envia alerta e ativa supressão.
- Permanecendo em estado problemático → suprime.
- Ao ver `running` → reseta supressão (próxima falha alertará novamente).
- `paused` em containers da allowlist → não alerta e não ativa supressão.

## 🔁 Onde se aplica

- Endpoint principal `/alert` (alertas do Grafana):
  - Integramos a supressão ao fluxo de containers, usando a melhor fonte de estado disponível (Portainer, quando habilitado; senão, heurística do alerta).
- Monitor ativo do Portainer:
  - Ao detectar quedas, também consulta a supressão antes de enviar; enquanto não voltar a `running`, não reenvia.

## 🧩 Como o estado é calculado

Ordem de preferência:

1. Portainer (quando habilitado): usa `running`, `Status/State` do container no endpoint.
2. Heurística do Grafana (fallback):
   - `status=firing` + `value=0` → `down`
   - `status=resolved` + `value=1` → `running`

## 🔐 Allowlist de Paused

Se você tem containers intencionalmente pausados, informe seus nomes/IDs em `CONTAINER_PAUSED_ALLOWLIST` para que:

- `paused` não gere alerta, e
- não ative a supressão (ou seja, se depois cair realmente, a 1ª falha ainda enviará alerta normalmente).

Exemplo:

```env
CONTAINER_PAUSED_ALLOWLIST=nginx_paused,batch-worker
```

## 🔧 Configuração

```env
# Ativa a supressão por estado (recomendado)
CONTAINER_SUPPRESS_REPEATS=true
# TTL (em segundos) do estado em memória
CONTAINER_SUPPRESS_TTL_SECONDS=86400
# Lista de containers permitidos em paused
CONTAINER_PAUSED_ALLOWLIST=nginx_paused,batch-worker
```

## 🧪 Exemplos práticos

- Loop de restarting:
  - `restarting` → envia 1 alerta e ativa supressão
  - continua `restarting` → não envia mais
  - volta para `running` → reseta
  - cai para `restarting` novamente → envia 1 alerta

- Paused intencional:
  - `paused` (em allowlist) → não envia, não ativa supressão
  - depois `down` → envia 1 alerta (primeira falha real)

## 📝 Logs úteis (DEBUG_MODE=true)

- No fluxo do Grafana:
  - `[DEBUG] Container suppression check: key=... state=... send=... reason=...`
- No PortainerMonitor:
  - `[DEBUG] PortainerMonitor: suppression tick key=... state=... send=... reason=...`
  - `[DEBUG] PortainerMonitor: suppression check key=... state=... send=... reason=...`

## ❓ Perguntas frequentes

- A supressão substitui o dedupe?
  - Não. O dedupe continua útil para payloads idênticos em janelas curtas. A supressão trava o reenvio por estado até ver `running`.
- O estado é persistido?
  - Em memória por processo (TTL configurável). Para persistência entre reinícios, considere Redis (podemos adicionar suporte se necessário).
