# 🎯 Melhorias de Clareza nos Alertas

**Data:** 2026-06-05  
**Objetivo:** Tornar os alertas mais claros, remover informações redundantes e melhorar o contexto de deployments Blue/Green

---

## ✨ O Que Foi Melhorado

### 1. **Alertas de Containers** ([formatters.py](app/formatters.py))

#### ✅ **Antes:**
- Muitas informações técnicas redundantes
- Campos vazios aparecendo
- Não ficava claro se era deploy Blue/Green ou falha real
- Informação de IP aparecia em 3 lugares diferentes

#### ✅ **Agora:**
```
🚨 ALERTA DE CONTAINER 🔥 🔵🟢 Blue/Green

🏷️ IDENTIFICAÇÃO
Container: nginx-blue (Ambiente: BLUE)
Host: 192.168.1.100
Fonte: portainer
🟢 Estado: running

📊 STATUS
Estado: 🔴 OFFLINE/PARADO

🔍 DETALHES
Service: web-service
Image: nginx

📝 ALERTA
Descrição: Container nginx-blue está OFFLINE (detectado via Portainer)
Status: FIRING • Hora: 2026-06-05 14:30:00
```

**Melhorias:**
- ✅ Indicador visual `🔵🟢 Blue/Green` no título quando é deploy
- ✅ Mostra ambiente (BLUE/GREEN) claramente
- ✅ Campos vazios removidos automaticamente
- ✅ Node só aparece se for diferente do host
- ✅ Health só aparece se tiver valor
- ✅ Image simplificada (remove registry/sha256 quando muito longa)
- ✅ Informações compactas em uma linha (Status + Hora juntos)

---

### 2. **Alertas de Métricas** (CPU/Memória/Disco) ([controller.py](app/controller.py))

#### ✅ **Antes:**
```
💾 ALERTA DE MEMÓRIA ⚠️

Nível: ALERTA
Servidor: 192.168.1.100
Prometheus: prometheus-main
Uso atual: 85%

Descrição: Memória alta detectada
Status: FIRING
Hora: 2026-06-05 14:30:00
```

#### ✅ **Agora:**
```
💾 ALERTA DE MEMÓRIA ⚠️

Nível: ALERTA • Uso: 85%
Host: 192.168.1.100

📝 Descrição: Memória alta detectada
Status: FIRING • Hora: 2026-06-05 14:30:00
```

**Melhorias:**
- ✅ Informações importantes na mesma linha (economiza espaço)
- ✅ Removido campo "Prometheus" (não relevante para o usuário final)
- ✅ Formato consistente em CPU, Memória e Disco
- ✅ Mais compacto e direto ao ponto

---

### 3. **Supressão Blue/Green** ([suppression.py](app/suppression.py))

#### ✅ **Melhorias na Lógica:**

1. **Período de Graça Mais Claro:**
   - Logs indicam quando período de graça inicia
   - Mostra tempo restante no DEBUG_MODE
   - Alerta claro quando período expira sem sibling subir

2. **Logs Melhorados:**
   ```
   [DEBUG] 🔵🟢 Suprimindo alerta de 'nginx-blue': sibling 'nginx-green' está ATIVO (deploy blue/green confirmado)
   
   [DEBUG] 🔵🟢 Iniciando período de graça de 120s para 'api-blue' (aguardando sibling 'api-green' subir)
   
   [DEBUG] 🔵🟢 Aguardando sibling 'api-green' subir: 45s/120s (faltam 75s)
   
   [DEBUG] 🔵🟢 ⚠️ Período de graça EXPIROU (125s) para 'api-blue' → sibling 'api-green' NÃO subiu, tratando como FALHA REAL
   ```

3. **Supressão Mais Inteligente:**
   - ✅ Detecta quando sibling está ativo → suprime alerta
   - ✅ Período de graça de 120s para aguardar deploy
   - ✅ Se sibling não sobe em 120s → alerta é enviado (falha real)
   - ✅ Logs indicam claramente o motivo da supressão

---

### 4. **PortainerMonitor** ([portainer_monitor.py](app/portainer_monitor.py))

#### ✅ **Alertas UP/DOWN Melhorados:**

1. **Embeds Simplificados:**
   ```
   ✅ Recuperação
   Endpoint: 4 • Estado: running • Tipo: Blue/Green (blue)
   
   🚨 Falha Detectada
   Endpoint: 4 • Estado: exited • Tipo: Blue/Green (green)
   ```

2. **Logs DEBUG Claros:**
   ```
   [DEBUG] PortainerMonitor: recuperação detectada - endpoint=4 container=nginx-blue
   [DEBUG] PortainerMonitor (🔵🟢 Blue/Green): suppression check key=192.168.1.100|nginx-blue state=running send=False reason=reset_on_running
   [DEBUG] PortainerMonitor: enviando alerta de UP (🔵🟢 Blue/Green) para nginx-blue (endpoint 4)
   ```

3. **Descrições Mais Claras:**
   - ✅ `"detectado via Portainer"` ao invés de só `"Portainer"`
   - ✅ Indica se é Blue/Green no contexto do alerta
   - ✅ Logs mostram tipo de container (regular vs Blue/Green)

---

### 5. **Logs DEBUG Consistentes** (Todos os arquivos)

#### ✅ **Indicadores Visuais:**
- `🔵🟢` = Blue/Green deployment
- `⏭️` = Alerta suprimido (normal)
- `⚠️` = Atenção/Warning
- `✅` = Recuperação/OK

#### ✅ **Formato Padronizado:**
```
[DEBUG] 🔵🟢 Suprimindo alerta de 'nginx-blue': sibling 'nginx-green' está ATIVO
[DEBUG] ⏭️ Alerta SUPRIMIDO: already_suppressed_until_running
[DEBUG] Suppression check para 'api-prod': state=down, send=true, reason=first_failure_since_running
```

---

## 🎯 Benefícios das Melhorias

### Para Ambiente com 20+ Endpoints e 100+ Containers:

1. **Menos Ruído:**
   - Alertas Blue/Green não geram spam durante deployments
   - Supressão inteligente evita repetições
   - Período de graça permite tempo para deploy completar

2. **Mais Clareza:**
   - Fácil identificar se é Blue/Green ou falha real
   - Informações importantes destacadas
   - Campos vazios não aparecem mais

3. **Melhor Troubleshooting:**
   - Logs DEBUG indicam exatamente por que alerta foi suprimido
   - Contexto Blue/Green sempre visível
   - Tempo de período de graça registrado

4. **Performance:**
   - Menos alertas = menos chamadas Discord API
   - Mensagens mais compactas = menos dados transferidos
   - Supressão em volume persiste entre restarts

---

## 🔧 Configuração Recomendada

Para aproveitar todas as melhorias:

```env
# Supressão Blue/Green (já habilitado por padrão)
BLUE_GREEN_SUPPRESSION_ENABLED=true
BLUE_GREEN_GRACE_SECONDS=120  # 2 minutos para deploy completar

# Monitoramento Portainer
PORTAINER_ACTIVE_MONITOR=true
PORTAINER_MONITOR_INTERVAL_SECONDS=30
PORTAINER_MONITOR_ONLY_SOURCE=true  # Ignora alertas de container do Grafana

# Persistência (essencial para 100+ containers)
CONTAINER_SUPPRESS_PERSIST=true
CONTAINER_SUPPRESS_STATE_FILE=/app/data/suppression-state.json

# Debug (para troubleshooting inicial)
DEBUG_MODE=true  # Desabilite em produção após validar
```

---

## 📝 Próximos Passos

1. **Testar em Ambiente de Dev:**
   ```bash
   docker-compose down
   docker-compose build
   docker-compose up -d
   docker logs grafana-discord-proxy-prod -f
   ```

2. **Validar Alertas:**
   - Verifique se alertas Blue/Green aparecem corretamente
   - Confirme que período de graça funciona (120s)
   - Valide que falhas reais não são suprimidas

3. **Ajustar se Necessário:**
   - Se 120s é pouco para seu deploy → aumentar `BLUE_GREEN_GRACE_SECONDS`
   - Se muitos alertas Blue/Green ainda passam → verificar nomenclatura dos containers
   - Se alertas muito verbosos → campos podem ser removidos em `formatters.py`

---

## ❓ Troubleshooting

### Problema: Alertas Blue/Green ainda sendo enviados

**Causa:** Container não segue padrão `nome-blue`/`nome-green`

**Solução:**
1. Verifique logs DEBUG para ver detecção:
   ```
   [DEBUG] Container 'nginx-blue' detectado como blue/green: base='nginx', color='blue'
   ```
2. Se não aparecer, renomeie containers para padrão correto:
   - ✅ `app-blue` / `app-green`
   - ✅ `nginx_blue` / `nginx_green`
   - ❌ `app-v1` / `app-v2` (não detectado)

### Problema: Período de graça muito curto

**Solução:**
```env
BLUE_GREEN_GRACE_SECONDS=300  # 5 minutos
```

### Problema: Logs muito verbosos

**Solução:**
```env
DEBUG_MODE=false  # Desabilita logs DEBUG
```

---

## 📊 Resumo Visual

| Aspecto | Antes | Agora |
|---------|-------|-------|
| **Campos vazios** | Apareciam | Removidos automaticamente |
| **Indicador Blue/Green** | ❌ Não havia | ✅ `🔵🟢` no título |
| **Informação de IP** | Em 3 lugares | Em 1 lugar (Host) |
| **Logs DEBUG** | Pouco claros | Com emojis e contexto |
| **Formato** | Verboso | Compacto e claro |
| **Supressão B/G** | Básica | Inteligente com período de graça |

---

**✅ Todas as melhorias foram implementadas e testadas sintaticamente.**  
**🚀 Sistema pronto para receber alertas mais claros e inteligentes!**
