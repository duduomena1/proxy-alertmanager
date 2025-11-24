# Solução: Persistência de Estado de Supressão

## Problema

Ao fazer rebuild da aplicação, todos os containers que estavam em estado `down` geravam alertas novamente, mesmo que você já estivesse ciente deles. Isso acontecia porque o estado de supressão era mantido apenas em memória e era perdido ao reiniciar a aplicação.

## Solução Implementada

Implementada **persistência do estado de supressão** em arquivo JSON, permitindo que o sistema "lembre" quais containers já geraram alertas e não envie novamente após restart.

### Como Funciona

1. **Salvamento Automático**: Sempre que o estado de um container muda (down, running, etc.), o estado é salvo em arquivo JSON
2. **Carregamento na Inicialização**: Ao iniciar a aplicação, o estado anterior é carregado automaticamente
3. **TTL Respeitado**: Apenas entradas dentro do TTL (padrão: 24h) são carregadas
4. **Limpeza Automática**: Entradas expiradas são removidas periodicamente

## Variáveis de Ambiente

### Novas Variáveis

```bash
# Habilita/desabilita persistência (padrão: true)
CONTAINER_SUPPRESS_PERSIST=true

# Caminho do arquivo de estado (padrão: /tmp/proxy-alertmanager-suppression-state.json)
CONTAINER_SUPPRESS_STATE_FILE=/tmp/proxy-alertmanager-suppression-state.json
```

### Variáveis Existentes (ainda válidas)

```bash
# Habilita supressão de alertas repetidos (padrão: true)
CONTAINER_SUPPRESS_REPEATS=true

# Tempo para expirar supressão (padrão: 86400 = 24h)
CONTAINER_SUPPRESS_TTL_SECONDS=86400
```

## Exemplo de Uso

### Cenário 1: Restart da Aplicação

**Antes do restart:**
```
Container nginx-blue: DOWN → Alerta enviado ✅
Container nginx-blue: DOWN → Alerta suprimido 🚫
Container nginx-blue: DOWN → Alerta suprimido 🚫
```

**[RESTART DA APLICAÇÃO]**

**Após o restart:**
```
Container nginx-blue: DOWN → Alerta suprimido 🚫 (estado carregado!)
Container nginx-blue: DOWN → Alerta suprimido 🚫
```

### Cenário 2: Container Volta a Running

```
Container app-blue: DOWN → Alerta enviado ✅
Container app-blue: DOWN → Alerta suprimido 🚫
Container app-blue: RUNNING → Reset da supressão
Container app-blue: DOWN → Alerta enviado ✅ (novo problema!)
```

## Estrutura do Arquivo de Estado

```json
{
  "192.168.1.100|id:abc123": {
    "suppressed": true,
    "last": "down",
    "ts": 1732428000.123
  },
  "192.168.1.101|id:def456": {
    "suppressed": false,
    "last": "running",
    "ts": 1732428100.456
  }
}
```

## Configuração Recomendada

### Para Ambiente de Produção

```bash
# Habilita persistência (recomendado)
CONTAINER_SUPPRESS_PERSIST=true

# Use caminho persistente (fora de /tmp se possível)
CONTAINER_SUPPRESS_STATE_FILE=/var/lib/proxy-alertmanager/suppression-state.json

# TTL de 24 horas (ajuste conforme necessário)
CONTAINER_SUPPRESS_TTL_SECONDS=86400
```

### Para Ambiente de Desenvolvimento

```bash
# Pode desabilitar persistência para testar alertas sempre
CONTAINER_SUPPRESS_PERSIST=false
```

### Docker Compose

```yaml
services:
  proxy-alertmanager:
    environment:
      - CONTAINER_SUPPRESS_PERSIST=true
      - CONTAINER_SUPPRESS_STATE_FILE=/app/data/suppression-state.json
    volumes:
      - ./data:/app/data  # Persiste o arquivo de estado
```

## Benefícios

✅ **Rebuild Limpo**: Não recebe spam de alertas já conhecidos após rebuild
✅ **Estado Consistente**: Mantém controle preciso do que já foi alertado
✅ **Configurável**: Pode ser desabilitado se necessário
✅ **Automático**: Funciona sem intervenção manual
✅ **Compatível**: Funciona com supressão blue/green e todas as outras features

## Testes

Execute o teste de persistência:

```bash
python test/test_suppression_persistence.py
```

Resultado esperado:
- ✅ Estado persiste entre instâncias
- ✅ Containers não geram alertas duplicados após restart
- ✅ Reset ao voltar a running é mantido

## Observações Importantes

1. **Primeira Execução**: Na primeira execução, não há estado salvo, então todos os containers down gerarão alertas (comportamento normal)

2. **Arquivo de Estado**: O arquivo é criado automaticamente. Certifique-se que o diretório tem permissão de escrita

3. **TTL**: Containers suprimidos há mais de TTL segundos serão limpos e gerarão novo alerta se ainda estiverem down

4. **Backup**: Em ambientes críticos, considere fazer backup do arquivo de estado

## Desabilitando a Persistência

Se preferir o comportamento antigo (estado apenas em memória):

```bash
export CONTAINER_SUPPRESS_PERSIST=false
```

Ou no Docker Compose:

```yaml
environment:
  - CONTAINER_SUPPRESS_PERSIST=false
```
