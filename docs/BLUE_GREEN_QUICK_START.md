# 🚀 Guia Rápido: Blue/Green Deployment Suppression

## 📋 Pré-requisitos

1. ✅ Portainer configurado e acessível
2. ✅ Containers seguindo nomenclatura `app-blue`/`app-green`
3. ✅ Par de containers no mesmo endpoint Portainer

## ⚙️ Configuração

### 1. Habilitar Portainer

```env
CONTAINER_VALIDATE_WITH_PORTAINER=true
PORTAINER_BASE_URL=https://portainer.local/api
PORTAINER_API_KEY=seu_token_portainer
PORTAINER_ENDPOINT_MAP_FILE=config/portainer_endpoints.json
```

### 2. Habilitar Blue/Green (já vem ativo por padrão)

```env
BLUE_GREEN_SUPPRESSION_ENABLED=true
```

### 3. Opcional: Debug detalhado

```env
DEBUG_MODE=true
```

## 📝 Nomenclatura Suportada

### ✅ Formatos Aceitos

| Padrão | Exemplo | Detectado |
|--------|---------|-----------|
| Hífen lowercase | `nginx-blue`, `nginx-green` | ✅ |
| Hífen uppercase | `NGINX-BLUE`, `NGINX-GREEN` | ✅ |
| Underscore lowercase | `api_blue`, `api_green` | ✅ |
| Underscore uppercase | `API_BLUE`, `API_GREEN` | ✅ |
| Mixed case | `Worker-Blue`, `Worker-Green` | ✅ |

### ❌ Formatos NÃO Detectados

| Padrão | Exemplo | Motivo |
|--------|---------|--------|
| Versão numérica | `app-v1`, `app-v2` | Não usa blue/green |
| Letra única | `app-a`, `app-b` | Não usa blue/green |
| Sem sufixo | `nginx`, `api` | Não é deployment blue/green |

## 🎯 Cenários de Uso

### Cenário 1: Deploy Normal (Blue → Green)

```
Estado Inicial:
  app-blue: running ✅
  app-green: stopped ❌

Ação: Deploy green
  app-blue: running ✅
  app-green: running ✅

Ação: Parar blue
  app-blue: stopped ❌  → ✅ Alerta SUPRIMIDO (green ativo)
  app-green: running ✅
```

### Cenário 2: Rollback (Green → Blue)

```
Estado Inicial:
  app-blue: stopped ❌
  app-green: running ✅

Ação: Subir blue
  app-blue: running ✅
  app-green: running ✅

Ação: Parar green
  app-blue: running ✅
  app-green: stopped ❌  → ✅ Alerta SUPRIMIDO (blue ativo)
```

### Cenário 3: Problema (Ambos Caem)

```
Estado Inicial:
  app-blue: running ✅
  app-green: stopped ❌

Ação: Blue cai
  app-blue: stopped ❌  → ⚠️ ALERTA ENVIADO (green não está ativo)
  app-green: stopped ❌

Ou: Ambos caem juntos
  app-blue: stopped ❌  → ⚠️ ALERTA ENVIADO
  app-green: stopped ❌  → ⚠️ ALERTA ENVIADO
```

## 🧪 Como Testar

### Teste Rápido com Script

```bash
# Executar script de testes
./test/test_blue_green_manual.sh

# Seguir instruções na tela para enviar payloads de teste
```

### Teste Manual via cURL

```bash
# 1. Container blue cai, green está ativo (deve SUPRIMIR)
curl -X POST http://localhost:5001/webhook/grafana \
  -H 'Content-Type: application/json' \
  -d '{
    "alerts": [{
      "status": "firing",
      "labels": {
        "container": "app-blue",
        "instance": "192.168.1.100:9100"
      },
      "values": {"A": 0}
    }]
  }'

# 2. Ambos caem (deve ALERTAR)
curl -X POST http://localhost:5001/webhook/grafana \
  -H 'Content-Type: application/json' \
  -d '{
    "alerts": [
      {
        "status": "firing",
        "labels": {"container": "app-blue", "instance": "192.168.1.100:9100"},
        "values": {"A": 0}
      },
      {
        "status": "firing",
        "labels": {"container": "app-green", "instance": "192.168.1.100:9100"},
        "values": {"A": 0}
      }
    ]
  }'
```

## 🔍 Verificação nos Logs

### Logs Esperados (DEBUG_MODE=true)

#### Supressão Ativa
```
[DEBUG] Container 'app-blue' detectado como blue/green: base='app', color='blue'
[DEBUG] Procurando sibling 'app-green' para container 'app-blue' no endpoint 15
[DEBUG] Sibling 'app-green' encontrado com estado 'running' (running=True)
[INFO] Suprimindo alerta de 'app-blue': sibling 'app-green' está ativo (blue/green deployment)
[DEBUG] Container suppression check: send=False reason=blue_green_sibling_active:app-green
```

#### Ambos Down (Alerta Enviado)
```
[DEBUG] Container 'app-blue' detectado como blue/green: base='app', color='blue'
[DEBUG] Procurando sibling 'app-green' para container 'app-blue' no endpoint 15
[DEBUG] Sibling 'app-green' encontrado com estado 'exited' (running=False)
[DEBUG] Container suppression check: send=True reason=first_failure_since_running
```

## 🛠️ Troubleshooting

### Problema: Alertas não estão sendo suprimidos

#### Checklist de Verificação

1. **Portainer habilitado?**
   ```bash
   # Verificar no .env
   grep CONTAINER_VALIDATE_WITH_PORTAINER .env
   # Deve retornar: CONTAINER_VALIDATE_WITH_PORTAINER=true
   ```

2. **Blue/Green habilitado?**
   ```bash
   grep BLUE_GREEN_SUPPRESSION_ENABLED .env
   # Deve retornar: BLUE_GREEN_SUPPRESSION_ENABLED=true (ou não ter a linha)
   ```

3. **Nomenclatura correta?**
   - Container usa `-blue` ou `-green`? ✅
   - Container usa `_blue` ou `_green`? ✅
   - Container usa outro padrão? ❌

4. **Mesmo endpoint?**
   - Verificar em `config/portainer_endpoints.json` se o host aponta para o mesmo endpoint

5. **Sibling realmente está rodando?**
   ```bash
   # Verificar no Portainer ou via Docker
   docker ps | grep "app-green"
   ```

### Problema: Alertas sendo suprimidos incorretamente

1. **Desabilitar temporariamente**
   ```env
   BLUE_GREEN_SUPPRESSION_ENABLED=false
   ```

2. **Verificar se não é problema de supressão por estado**
   - A supressão normal (não blue/green) também pode estar ativa
   - Verificar: `CONTAINER_SUPPRESS_REPEATS=true`

3. **Checar allowlists**
   ```env
   # Containers que nunca devem ser suprimidos
   CONTAINER_ALWAYS_NOTIFY_ALLOWLIST=app-blue,app-green
   ```

## 📊 Comandos Úteis

### Ver estado dos containers no Portainer
```bash
# Via API (substitua valores)
curl -H "X-API-Key: $PORTAINER_API_KEY" \
  "$PORTAINER_BASE_URL/endpoints/15/docker/containers/json?all=1" \
  | jq '.[] | {name: .Names[0], state: .State}'
```

### Monitorar logs da aplicação
```bash
# Docker
docker logs -f proxy-alertmanager

# Direto
tail -f logs/app.log
```

### Testar conectividade com Portainer
```bash
curl -H "X-API-Key: $PORTAINER_API_KEY" \
  "$PORTAINER_BASE_URL/endpoints" \
  | jq '.'
```

## 🎓 Boas Práticas

### ✅ Recomendações

1. **Usar nomenclatura consistente**: Escolha hífen ou underscore e mantenha
2. **Habilitar DEBUG em desenvolvimento**: Facilita troubleshooting
3. **Monitorar logs inicialmente**: Validar comportamento nos primeiros deploys
4. **Documentar endpoints**: Manter `portainer_endpoints.json` atualizado
5. **Testar antes de produção**: Validar com payloads de teste

### ❌ Evitar

1. **Misturar nomenclaturas**: Não use `app-blue` e `app_green` no mesmo par
2. **Endpoints diferentes**: Par deve estar no mesmo endpoint
3. **Desabilitar Portainer**: Feature requer Portainer ativo
4. **Nomes muito longos**: Preferir nomes curtos e descritivos

## 🔄 Integração com CI/CD

### Exemplo: GitLab CI

```yaml
deploy:
  script:
    # 1. Subir novo container
    - docker-compose up -d app-green
    
    # 2. Aguardar health check
    - sleep 10
    
    # 3. Parar antigo (alerta será suprimido automaticamente)
    - docker-compose stop app-blue
    
    # 4. Limpar antigo após validação
    - docker-compose rm -f app-blue
```

### Exemplo: Script Bash

```bash
#!/bin/bash
# deploy.sh - Deploy blue/green automatizado

CURRENT=$(docker ps --filter "name=app-blue" -q)
NEW_COLOR="green"

if [ -n "$CURRENT" ]; then
    NEW_COLOR="blue"
fi

echo "Deploying app-${NEW_COLOR}..."
docker-compose up -d app-${NEW_COLOR}

echo "Waiting for health check..."
sleep 15

OLD_COLOR=$([[ "$NEW_COLOR" == "blue" ]] && echo "green" || echo "blue")
echo "Stopping app-${OLD_COLOR}..."
docker-compose stop app-${OLD_COLOR}

echo "Deploy complete! Alert suppression will handle notifications."
```

## 📚 Referências

- [Documentação ENV_VARS.md](../docs/ENV_VARS.md) - Todas as variáveis de ambiente
- [IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md) - Detalhes da implementação
- [CHANGELOG.md](../CHANGELOG.md) - Histórico de versões
- [test_blue_green_manual.sh](test_blue_green_manual.sh) - Script de testes

## 💡 Dicas Finais

1. **Primeira vez?** Ative `DEBUG_MODE=true` e monitore os logs durante o primeiro deploy
2. **Problemas?** Desabilite temporariamente com `BLUE_GREEN_SUPPRESSION_ENABLED=false`
3. **Dúvidas?** Revise os logs de debug, eles mostram todo o processo de decisão
4. **Performance?** A feature adiciona apenas 1 chamada à API Portainer quando necessário

---

✅ **Feature pronta para uso em produção!**
