# 🚀 Grafana Discord Proxy

Um proxy inteligente e personalizável para enviar alertas do Grafana para o Discord com formatação elegante e suporte a GIFs animados.

## ✨ Características

- 🎯 **Detecção Automática**: Identifica automaticamente o tipo de alerta (CPU, Memória, Disco, Container)
- 🎨 **Personalizável**: Configure cores e GIFs específicos para cada tipo de alerta
- 📱 **Formatação Clara**: Mensagens organizadas e fáceis de ler no Discord
- 🐳 **Docker Ready**: Containerizado e pronto para deploy
- 🔧 **Configuração Flexível**: Todas as configurações via variáveis de ambiente
- 🔍 **Health Check**: Endpoint de monitoramento incluído

## 🚦 Tipos de Alertas Suportados

| Tipo | Emoji | Detecta por | Exemplo |
|------|--------|-------------|---------|
| **CPU** | 🖥️ | `cpu`, `processor`, `load` | Uso de CPU alto |
| **Memória** | 💾 | `memory`, `mem`, `ram` | Uso de RAM alto |
| **Disco** | 💿 | `disk`, `storage`, `filesystem` | Disco cheio |
| **Container** | 🐳 | `container`, `docker`, `pod` | Container parado |
| **Padrão** | 🚨 | Outros tipos | Alertas genéricos |

## 📋 Pré-requisitos

- Docker e Docker Compose
- Webhook do Discord configurado
- Grafana configurado para enviar alertas via webhook

## ⚙️ Configuração Rápida

### 1. Clone e Configure

```bash
git clone <seu-repositorio>
cd proxy-alertmanager

# Copie o arquivo de exemplo
cp .env.example .env

# Edite as configurações
nano .env
```

### 2. Configure seu Webhook do Discord

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/SEU_WEBHOOK_AQUI
```

### 3. Execute com Docker

```bash
# Build e start
docker-compose up -d

# Verificar logs
docker-compose logs -f grafana-discord-proxy
```

### 4. Configure o Grafana

No Grafana, configure um **Contact Point** com:
- **Type**: Webhook
- **URL**: `http://IP_DO_SERVIDOR:5001/alert`
- **HTTP Method**: POST

## 🎨 Personalização de Alertas

### Configuração de GIFs

Adicione URLs de GIFs para cada tipo de alerta no `.env`:

```env
# GIFs para cada tipo de alerta
CPU_ALERT_GIF=https://media.giphy.com/media/xT9IgzoKnwFNmISR8I/giphy.gif
MEMORY_ALERT_GIF=https://media.giphy.com/media/3oKIPnAiaMCws8nOsE/giphy.gif
DISK_ALERT_GIF=https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif
CONTAINER_ALERT_GIF=https://media.giphy.com/media/xT9IgG50Fb7Mi0prBC/giphy.gif
```

### Configuração de Cores

Personalize as cores dos embeds (formato decimal):

```env
# Cores para alertas ativos (firing)
CPU_COLOR_FIRING=16776960      # Amarelo
MEMORY_COLOR_FIRING=16744192   # Rosa  
DISK_COLOR_FIRING=16711680     # Vermelho
CONTAINER_COLOR_FIRING=16753920 # Laranja

# Cores para alertas resolvidos
*_COLOR_RESOLVED=65280          # Verde para todos
```

## 📊 Exemplo de Saída

### Alerta de Disco
```
💿 **ALERTA DE DISCO**

**Servidor:** `10.2.100.13`
**Dispositivo:** `/dev/mapper/tatico--candeias--vg-root`
**Ponto de montagem:** `/`
**Uso atual:** `83.3%`

**Descrição:** ⚠️ O uso do disco acima de 80%
**Status:** FIRING
**Hora:** 2025-10-03 13:44:00
```

### Alerta de CPU
```
🖥️ **ALERTA DE CPU**

**Servidor:** `10.2.100.13`
**Uso atual:** `85.2%`

**Descrição:** Uso de CPU crítico
**Status:** FIRING
**Hora:** 2025-10-03 14:15:30
```

## 🔧 Configurações Avançadas

### Modo Debug

Ative logs detalhados:

```env
DEBUG_MODE=true
```

### Porta Personalizada

```env
APP_PORT=8080
```

### Health Check

Verifique se o serviço está funcionando:

```bash
curl http://localhost:5001/health
```

## 🐳 Deploy em Produção

### Com Grafana Existente

Se já tem Grafana rodando, use a rede dele:

```yaml
# docker-compose.yml
networks:
  grafana_default:
    external: true
```

### Monitoramento

O container inclui health check automático:

```bash
# Ver status do health check
docker ps
```

## 🛠️ Desenvolvimento Local

```bash
# Instalar dependências
pip install -r requirements.txt

# Executar em modo desenvolvimento
export DEBUG_MODE=true
python discord_proxy.py
```

## 📝 Estrutura do Projeto

```
proxy-alertmanager/
├── discord_proxy.py      # Aplicação principal
├── requirements.txt      # Dependências Python
├── Dockerfile           # Configuração do container
├── docker-compose.yml   # Orquestração dos serviços
├── .env.example        # Exemplo de configurações
└── README.md           # Este arquivo
```

## 🔍 Troubleshooting

### Alertas não chegam no Discord

1. Verifique se o webhook URL está correto
2. Confirme se o Grafana consegue acessar a URL do proxy
3. Verifique os logs: `docker-compose logs grafana-discord-proxy`

### Cores não aparecem

Certifique-se de usar o formato decimal correto:
- Vermelho: `16711680`
- Verde: `65280`
- Azul: `255`

### GIFs não aparecem

1. Verifique se a URL do GIF é válida
2. Teste a URL diretamente no navegador
3. Alguns serviços podem bloquear hotlinking

## 🤝 Contribuição

Sinta-se à vontade para:
- Reportar bugs
- Sugerir melhorias
- Enviar pull requests
- Adicionar novos tipos de alertas

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo `LICENSE` para mais detalhes.

---

**Desenvolvido com ❤️ para melhorar a experiência de monitoramento**