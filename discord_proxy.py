from flask import Flask, request
import requests
import os
import re
from datetime import datetime

app = Flask(__name__)

# Configurações do ambiente
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
APP_PORT = int(os.getenv("APP_PORT", "5001"))
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"

# GIFs e cores para diferentes tipos de alertas
ALERT_CONFIGS = {
    "cpu": {
        "emoji": "🖥️",
        "gif": os.getenv("CPU_ALERT_GIF", ""),
        "color_firing": int(os.getenv("CPU_COLOR_FIRING", "16776960")),  # Amarelo
        "color_resolved": int(os.getenv("CPU_COLOR_RESOLVED", "65280"))   # Verde
    },
    "memory": {
        "emoji": "💾",
        "gif": os.getenv("MEMORY_ALERT_GIF", ""),
        "color_firing": int(os.getenv("MEMORY_COLOR_FIRING", "16744192")),  # Rosa
        "color_resolved": int(os.getenv("MEMORY_COLOR_RESOLVED", "65280"))    # Verde
    },
    "disk": {
        "emoji": "💿",
        "gif": os.getenv("DISK_ALERT_GIF", ""),
        "color_firing": int(os.getenv("DISK_COLOR_FIRING", "16711680")),   # Vermelho
        "color_resolved": int(os.getenv("DISK_COLOR_RESOLVED", "65280"))     # Verde
    },
    "container": {
        "emoji": "🐳",
        "gif": os.getenv("CONTAINER_ALERT_GIF", ""),
        "color_firing": int(os.getenv("CONTAINER_COLOR_FIRING", "16753920")),  # Laranja
        "color_resolved": int(os.getenv("CONTAINER_COLOR_RESOLVED", "65280"))    # Verde
    },
    "default": {
        "emoji": "🚨",
        "gif": os.getenv("DEFAULT_ALERT_GIF", ""),
        "color_firing": int(os.getenv("DEFAULT_COLOR_FIRING", "16711680")),   # Vermelho
        "color_resolved": int(os.getenv("DEFAULT_COLOR_RESOLVED", "65280"))     # Verde
    }
}

@app.route('/health', methods=['GET'])
def health():
    """Endpoint para health check"""
    return {'status': 'ok', 'service': 'grafana-discord-proxy'}, 200

@app.route('/alert', methods=['POST'])
def alert():
    try:
        data = request.json
        if DEBUG_MODE:
            print(f"[DEBUG] Received data: {data}")
        
        # Verifica se é um alerta do Grafana com o novo formato
        if 'alerts' in data and len(data['alerts']) > 0:
            return handle_grafana_alert(data)
        
        # Fallback para o formato antigo
        return handle_legacy_alert(data)
    except Exception as e:
        if DEBUG_MODE:
            print(f"[ERROR] {str(e)}")
        return f'Error: {str(e)}', 500

def detect_alert_type(labels, annotations, alertname):
    """Detecta o tipo de alerta baseado nos dados recebidos"""
    alertname_lower = alertname.lower()
    description_lower = annotations.get('description', '').lower()
    
    # Verifica por palavras-chave específicas
    if any(keyword in alertname_lower for keyword in ['cpu', 'processor', 'load']):
        return 'cpu'
    elif any(keyword in alertname_lower for keyword in ['memory', 'mem', 'ram']):
        return 'memory'
    elif any(keyword in alertname_lower for keyword in ['disk', 'storage', 'filesystem']) or 'device' in labels:
        return 'disk'
    elif any(keyword in alertname_lower for keyword in ['container', 'docker', 'pod']):
        return 'container'
    elif 'cpu' in description_lower:
        return 'cpu'
    elif any(keyword in description_lower for keyword in ['memory', 'mem', 'ram']):
        return 'memory'
    elif any(keyword in description_lower for keyword in ['disk', 'disco']):
        return 'disk'
    
    return 'default'

def format_timestamp(timestamp_str):
    """Formata timestamp para formato brasileiro"""
    if not timestamp_str or timestamp_str == 'N/A':
        return 'N/A'
    try:
        # Remove Z e converte para datetime
        clean_timestamp = timestamp_str.replace('Z', '').replace('T', ' ')
        return clean_timestamp
    except:
        return timestamp_str

def get_metric_value(values):
    """Extrai o valor principal da métrica"""
    if not values:
        return 0
    
    # Tenta pegar o valor A primeiro, depois C, depois qualquer outro
    if 'A' in values and values['A'] is not None:
        return float(values['A'])
    elif 'C' in values and values['C'] is not None:
        return float(values['C'])
    else:
        # Pega o primeiro valor não nulo
        for key, value in values.items():
            if value is not None:
                return float(value)
    return 0

def handle_grafana_alert(data):
    """Processa alertas do Grafana no novo formato"""
    
    # Processa múltiplos alertas se houver
    processed_alerts = []
    
    for alert_data in data['alerts']:
        labels = alert_data.get('labels', {})
        annotations = alert_data.get('annotations', {})
        values = alert_data.get('values', {})
        
        # Detecta o tipo de alerta
        alertname = labels.get('alertname', 'Alerta')
        alert_type = detect_alert_type(labels, annotations, alertname)
        config = ALERT_CONFIGS.get(alert_type, ALERT_CONFIGS['default'])
        
        # Extrai informações comuns
        instance = labels.get('instance', 'N/A').split(':')[0] if labels.get('instance') else 'N/A'
        device = labels.get('device', labels.get('container', labels.get('job', 'N/A')))
        mountpoint = labels.get('mountpoint', '/')
        
        # Pega o valor da métrica
        metric_value = get_metric_value(values)
        
        # Extrai descrição
        description = annotations.get('description', '').replace('"', '').strip()
        if not description:
            description = annotations.get('summary', 'Sem descrição disponível')
        
        # Status do alerta individual
        alert_status = alert_data.get('status', 'unknown')
        is_firing = alert_status == 'firing'
        
        # Monta mensagem específica por tipo
        if alert_type == 'disk':
            content = f"""{config['emoji']} **ALERTA DE DISCO**

**Servidor:** `{instance}`
**Dispositivo:** `{device}`
**Ponto de montagem:** `{mountpoint}`
**Uso atual:** `{metric_value:.1f}%`

**Descrição:** {description}
**Status:** {alert_status.upper()}
**Hora:** {format_timestamp(alert_data.get('startsAt', 'N/A'))}"""
            
        elif alert_type == 'cpu':
            content = f"""{config['emoji']} **ALERTA DE CPU**

**Servidor:** `{instance}`
**Uso atual:** `{metric_value:.1f}%`

**Descrição:** {description}
**Status:** {alert_status.upper()}
**Hora:** {format_timestamp(alert_data.get('startsAt', 'N/A'))}"""
            
        elif alert_type == 'memory':
            content = f"""{config['emoji']} **ALERTA DE MEMÓRIA**

**Servidor:** `{instance}`
**Uso atual:** `{metric_value:.1f}%`

**Descrição:** {description}
**Status:** {alert_status.upper()}
**Hora:** {format_timestamp(alert_data.get('startsAt', 'N/A'))}"""
            
        elif alert_type == 'container':
            content = f"""{config['emoji']} **ALERTA DE CONTAINER**

**Servidor:** `{instance}`
**Container:** `{device}`
**Valor:** `{metric_value:.1f}`

**Descrição:** {description}
**Status:** {alert_status.upper()}
**Hora:** {format_timestamp(alert_data.get('startsAt', 'N/A'))}"""
            
        else:  # default
            content = f"""{config['emoji']} **ALERTA DO SISTEMA**

**Servidor:** `{instance}`
**Componente:** `{device}`
**Valor:** `{metric_value:.1f}`

**Descrição:** {description}
**Status:** {alert_status.upper()}
**Hora:** {format_timestamp(alert_data.get('startsAt', 'N/A'))}"""
        
        # Monta embed
        embed = {
            "color": config['color_firing'] if is_firing else config['color_resolved'],
            "fields": [
                {
                    "name": "Detalhes Técnicos",
                    "value": f"**Alert:** {alertname}\n**Instance:** {labels.get('instance', 'N/A')}",
                    "inline": True
                }
            ]
        }
        
        # Adiciona GIF se configurado
        if config['gif']:
            embed["image"] = {"url": config['gif']}
        
        processed_alerts.append({
            "content": content,
            "embed": embed,
            "type": alert_type,
            "status": alert_status
        })
    
    # Envia alertas para o Discord
    for alert in processed_alerts:
        payload = {
            "content": alert["content"],
            "embeds": [alert["embed"]]
        }
        
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        if DEBUG_MODE:
            print(f"[DEBUG] Sent {alert['type']} alert, status: {resp.status_code}")
    
    return '', 200

def handle_legacy_alert(data):
    """Processa alertas no formato antigo (compatibilidade)"""
    title = data.get('title', 'Alerta!')
    message = data.get('message', '')
    eval_matches = data.get('evalMatches', [])
    metric_info = ""
    gif_url = data.get('gif', '')

    # Monta info das métricas disparadas
    for match in eval_matches:
        metric = match.get('metric', 'Métrica')
        value = match.get('value', 'N/A')
        tags = match.get('tags', {})
        tagstr = ', '.join([f"{k}: {v}" for k, v in tags.items()])
        metric_info += f"\n**{metric}**: `{value}` {tagstr}"

    # Monta o payload do Discord
    payload = {
        "content": f"🚨 **{title}**\n{message}{metric_info}",
        "embeds": []
    }

    # Adiciona GIF se houver
    if gif_url:
        payload["embeds"].append({
            "image": {
                "url": gif_url
            }
        })

    # Envia para o Discord
    resp = requests.post(DISCORD_WEBHOOK_URL, json=payload)
    return '', resp.status_code

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=APP_PORT, debug=DEBUG_MODE)