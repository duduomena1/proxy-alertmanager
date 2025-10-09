from flask import Flask, request
import requests
import os
import re
from datetime import datetime
import json

app = Flask(__name__)

# Configurações do ambiente
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
APP_PORT = int(os.getenv("APP_PORT", "5001"))
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"

# Configurações de tipos de alertas com níveis de severidade
ALERT_CONFIGS = {
    "cpu": {
        "emoji": "🖥️",
        "name": "CPU",
        "unit": "%"
    },
    "memory": {
        "emoji": "💾",
        "name": "MEMÓRIA",
        "unit": "%"
    },
    "disk": {
        "emoji": "💿",
        "name": "DISCO",
        "unit": "%"
    },
    "container": {
        "emoji": "🐳",
        "name": "CONTAINER",
        "unit": ""
    },
    "default": {
        "emoji": "🚨",
        "name": "SISTEMA",
        "unit": ""
    }
}

# Configurações de severidade baseadas no valor da métrica
SEVERITY_LEVELS = {
    "low": {
        "threshold_min": 0,
        "threshold_max": 80,
        "emoji": "⚠️",
        "label": "ATENÇÃO",
        "colors": {
            "cpu": int(os.getenv("CPU_LOW_COLOR", "16776960")),      # Amarelo
            "memory": int(os.getenv("MEMORY_LOW_COLOR", "16776960")),  # Amarelo
            "disk": int(os.getenv("DISK_LOW_COLOR", "16776960")),     # Amarelo

            "default": int(os.getenv("DEFAULT_LOW_COLOR", "16776960"))   # Amarelo
        },
        "gifs": {
            "cpu": os.getenv("CPU_LOW_GIF", ""),
            "memory": os.getenv("MEMORY_LOW_GIF", ""),
            "disk": os.getenv("DISK_LOW_GIF", ""),
            "default": os.getenv("DEFAULT_LOW_GIF", "")
        }
    },
    "medium": {
        "threshold_min": 80,
        "threshold_max": 90,
        "emoji": "🚧",
        "label": "ALERTA",
        "colors": {
            "cpu": int(os.getenv("CPU_MEDIUM_COLOR", "16753920")),      # Laranja
            "memory": int(os.getenv("MEMORY_MEDIUM_COLOR", "16753920")),  # Laranja
            "disk": int(os.getenv("DISK_MEDIUM_COLOR", "16753920")),     # Laranja
            "default": int(os.getenv("DEFAULT_MEDIUM_COLOR", "16753920"))   # Laranja
        },
        "gifs": {
            "cpu": os.getenv("CPU_MEDIUM_GIF", ""),
            "memory": os.getenv("MEMORY_MEDIUM_GIF", ""),
            "disk": os.getenv("DISK_MEDIUM_GIF", ""),
            "default": os.getenv("DEFAULT_MEDIUM_GIF", "")
        }
    },
    "high": {
        "threshold_min": 90,
        "threshold_max": 100,
        "emoji": "🔥",
        "label": "CRÍTICO",
        "colors": {
            "cpu": int(os.getenv("CPU_HIGH_COLOR", "16711680")),      # Vermelho
            "memory": int(os.getenv("MEMORY_HIGH_COLOR", "16711680")),  # Vermelho
            "disk": int(os.getenv("DISK_HIGH_COLOR", "16711680")),     # Vermelho
            "default": int(os.getenv("DEFAULT_HIGH_COLOR", "16711680"))   # Vermelho
        },
        "gifs": {
            "cpu": os.getenv("CPU_HIGH_GIF", ""),
            "memory": os.getenv("MEMORY_HIGH_GIF", ""),
            "disk": os.getenv("DISK_HIGH_GIF", ""),
            "default": os.getenv("DEFAULT_HIGH_GIF", "")
        }
    },
    "container_down": {
        "emoji": "🚨",
        "label": "CONTAINER OFFLINE",
        "color": int(os.getenv("CONTAINER_DOWN_COLOR", "16711680")),  # Vermelho
        "gif": os.getenv("CONTAINER_DOWN_GIF", "")
    },
    "container_up": {
        "emoji": "✅",
        "label": "CONTAINER ONLINE",
        "color": int(os.getenv("CONTAINER_UP_COLOR", "65280")),  # Verde
        "gif": os.getenv("CONTAINER_UP_GIF", "")
    },
    "resolved": {
        "emoji": "✅",
        "label": "RESOLVIDO",
        "color": int(os.getenv("RESOLVED_COLOR", "65280")),  # Verde
        "gif": os.getenv("RESOLVED_GIF", "")
    }
}

def extract_real_ip_and_source(labels):
    """Extrai IP real e fonte do Prometheus usando múltiplas estratégias"""
    
    real_ip = None
    prometheus_source = "unknown"
    original_instance = labels.get('instance', 'N/A')
    
    # 1. Identificar fonte do Prometheus (incluindo novas tags)
    if labels.get('prometheus_server'):
        prometheus_source = labels['prometheus_server']
    elif labels.get('prometheus'):
        prometheus_source = labels['prometheus']
    elif labels.get('prometheus_replica'):
        prometheus_source = labels['prometheus_replica']
    elif labels.get('receive'):
        prometheus_source = labels['receive']
    
    # 2. Buscar IP real em ordem de prioridade (incluindo novas tags do Prometheus)
    ip_candidates = [
        labels.get('host_ip'),            # Nova tag do Prometheus atualizado
        labels.get('real_host'),          # Nova tag do Prometheus atualizado  
        labels.get('__address__'),        # IP original antes do relabeling
        labels.get('instance'),           # Instance atual
        labels.get('kubernetes_node'),    # Node do K8s
        labels.get('node_name'),          # Nome do node
        labels.get('host'),               # Host label
        labels.get('hostname'),           # Hostname
        labels.get('target')              # Target do scrape
    ]
    
    for candidate in ip_candidates:
        if candidate and candidate != 'N/A':
            # Extrair IP se estiver no formato IP:porta
            ip_match = re.match(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', candidate)
            if ip_match:
                real_ip = ip_match.group(1)
                break
            # Se não é IP, mas é um hostname válido, mantém
            elif not candidate.startswith('node-exporter') and ':' in candidate:
                # Remove porta se houver
                real_ip = candidate.split(':')[0]
                break
    
    return {
        'real_ip': real_ip,
        'prometheus_source': prometheus_source,
        'original_instance': original_instance,
        'clean_host': real_ip if real_ip else original_instance.split(':')[0] if ':' in original_instance else original_instance
    }

def extract_metric_value_enhanced(values, value_string):
    """Extrai valor de métrica com fallback aprimorado para valueString"""
    
    # Primeiro tenta extrair dos values
    if values and isinstance(values, dict):
        # Prioridade: A, C, B, D, qualquer outro
        for key in ['A', 'C', 'B', 'D']:
            if key in values and values[key] is not None:
                try:
                    return float(values[key])
                except (ValueError, TypeError):
                    continue
        
        # Se não encontrou nas chaves prioritárias, pega qualquer valor válido
        for key, value in values.items():
            if value is not None:
                try:
                    return float(value)
                except (ValueError, TypeError):
                    continue
    
    # Fallback: extrair do valueString
    if value_string:
        try:
            # Padrão específico do Grafana: "value=16.002551672152055"
            value_match = re.search(r'value=([0-9]*\.?[0-9]+)', str(value_string))
            if value_match:
                return float(value_match.group(1))
            
            # Fallback: qualquer número decimal
            number_match = re.search(r'([0-9]*\.?[0-9]+)', str(value_string))
            if number_match:
                return float(number_match.group(1))
                
        except (ValueError, AttributeError):
            pass
    
    return 0.0

def enrich_alert_data(alert_data):
    """Enriquece dados do alerta com informações adicionais para melhor rastreamento"""
    
    for alert in alert_data.get('alerts', []):
        labels = alert.get('labels', {})
        
        # Extrai informações de IP e origem
        ip_info = extract_real_ip_and_source(labels)
        
        # Adiciona ao alert para uso posterior
        alert['enriched_data'] = {
            'real_ip': ip_info['real_ip'],
            'prometheus_source': ip_info['prometheus_source'],
            'original_instance': ip_info['original_instance'],
            'clean_host': ip_info['clean_host'],
            'timestamp_processed': datetime.now().isoformat()
        }
        
        # Para containers, adicionar contexto extra
        if is_container_alert(labels):
            alert['enriched_data']['container_context'] = {
                'container_name': labels.get('container', labels.get('container_name', labels.get('job'))),
                'namespace': labels.get('namespace', 'default'),
                'pod': labels.get('pod'),
                'service': labels.get('service')
            }
    
    return alert_data

def is_container_alert(labels):
    """Verifica se é um alerta relacionado a container"""
    container_indicators = [
        labels.get('container'),
        labels.get('container_name'),
        'container' in labels.get('job', '').lower(),
        'docker' in labels.get('job', '').lower(),
        'pod' in labels.get('job', '').lower(),
        labels.get('pod')
    ]
    return any(indicator for indicator in container_indicators)

def get_severity_level(metric_value, alert_type="default"):
    """Determina o nível de severidade baseado no valor da métrica"""
    
    # Container tem lógica específica: 0 = down, 1 = up
    if alert_type == "container":
        if metric_value == 0:
            return "container_down"
        else:
            return "container_up"
    
    # Para outros tipos, usa percentuais
    if metric_value < 80:
        return "low"
    elif 80 <= metric_value < 90:
        return "medium"
    else:
        return "high"

def get_severity_config(severity_level, alert_type="default"):
    """Retorna as configurações de cor e GIF para o nível de severidade"""
    
    # Configurações especiais para containers
    if severity_level in ["container_down", "container_up", "resolved"]:
        level_config = SEVERITY_LEVELS[severity_level]
        return {
            "emoji": level_config["emoji"],
            "label": level_config["label"],
            "color": level_config["color"],
            "gif": level_config["gif"]
        }
    
    # Configurações para níveis baseados em percentual
    level_config = SEVERITY_LEVELS.get(severity_level, SEVERITY_LEVELS["low"])
    return {
        "emoji": level_config["emoji"],
        "label": level_config["label"],
        "color": level_config["colors"].get(alert_type, level_config["colors"]["default"]),
        "gif": level_config["gifs"].get(alert_type, level_config["gifs"]["default"])
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
    service_type = labels.get('service_type', '').lower()
    
    # Prioridade 1: Verifica pelo service_type do Prometheus
    if 'postgres' in service_type:
        return 'default'  # PostgreSQL pode ter alertas específicos futuramente
    elif 'container' in service_type or 'docker' in service_type:
        return 'container'
    elif 'node' in service_type:
        # Para node-exporter, detecta pelo device ou nome do alerta
        if 'device' in labels or any(keyword in alertname_lower for keyword in ['disk', 'storage', 'filesystem']):
            return 'disk'
        elif any(keyword in alertname_lower for keyword in ['memory', 'mem', 'ram']):
            return 'memory'
        elif any(keyword in alertname_lower for keyword in ['cpu', 'processor', 'load']):
            return 'cpu'
    
    # Prioridade 2: Verifica por palavras-chave específicas no alertname
    if any(keyword in alertname_lower for keyword in ['cpu', 'processor', 'load']):
        return 'cpu'
    elif any(keyword in alertname_lower for keyword in ['memory', 'mem', 'ram']):
        return 'memory'
    elif any(keyword in alertname_lower for keyword in ['disk', 'storage', 'filesystem']) or 'device' in labels:
        return 'disk'
    elif any(keyword in alertname_lower for keyword in ['container', 'docker', 'pod']):
        return 'container'
    
    # Prioridade 3: Verifica na descrição
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

def get_metric_value(values, value_string=None):
    """Extrai o valor principal da métrica com fallback para valueString"""
    # Usa a função aprimorada
    return extract_metric_value_enhanced(values, value_string)

def handle_grafana_alert(data):
    """Processa alertas do Grafana no novo formato"""
    
    # ENRIQUECE os dados antes do processamento
    enriched_data = enrich_alert_data(data)
    
    # Processa múltiplos alertas se houver
    processed_alerts = []
    
    for alert_data in enriched_data['alerts']:
        labels = alert_data.get('labels', {})
        annotations = alert_data.get('annotations', {})
        values = alert_data.get('values', {})
        value_string = alert_data.get('valueString', '')
        enriched_info = alert_data.get('enriched_data', {})
        
        # Detecta o tipo de alerta
        alertname = labels.get('alertname', 'Alerta')
        alert_type = detect_alert_type(labels, annotations, alertname)
        config = ALERT_CONFIGS.get(alert_type, ALERT_CONFIGS['default'])
        
        # USA informações enriquecidas para melhor identificação
        real_ip = enriched_info.get('real_ip')
        clean_host = enriched_info.get('clean_host', 'unknown')
        prometheus_source = enriched_info.get('prometheus_source', 'unknown')
        
        # Informações específicas do alerta
        device = labels.get('device', labels.get('container', labels.get('job', 'N/A')))
        mountpoint = labels.get('mountpoint', '/')
        
        # EXTRAI valor com fallback aprimorado
        metric_value = get_metric_value(values, value_string)
        
        # Extrai descrição
        description = annotations.get('description', '').replace('"', '').strip()
        if not description:
            description = annotations.get('summary', 'Sem descrição disponível')
        
        # Status do alerta individual
        alert_status = alert_data.get('status', 'unknown')
        is_firing = alert_status == 'firing'
        
        # Determina o nível de severidade baseado no valor e status
        if is_firing:
            severity_level = get_severity_level(metric_value, alert_type)
        else:
            severity_level = "resolved"
        
        # Pega as configurações de severidade
        severity_config = get_severity_config(severity_level, alert_type)
        
        # Monta mensagem específica por tipo
        if alert_type == 'disk':
            content = f"""{config['emoji']} **ALERTA DE {config['name']}** {severity_config['emoji']}

**Nível:** `{severity_config['label']}`
**Servidor:** `{real_ip if real_ip else clean_host}`
**Prometheus:** `{prometheus_source}`
**Dispositivo:** `{device}`
**Ponto de montagem:** `{mountpoint}`
**Uso atual:** `{metric_value:.1f}{config['unit']}`

**Descrição:** {description}
**Status:** {alert_status.upper()}
**Hora:** {format_timestamp(alert_data.get('startsAt', 'N/A'))}"""
            
        elif alert_type == 'cpu':
            content = f"""{config['emoji']} **ALERTA DE {config['name']}** {severity_config['emoji']}

**Nível:** `{severity_config['label']}`
**Servidor:** `{real_ip if real_ip else clean_host}`
**Prometheus:** `{prometheus_source}`
**Uso atual:** `{metric_value:.1f}{config['unit']}`

**Descrição:** {description}
**Status:** {alert_status.upper()}
**Hora:** {format_timestamp(alert_data.get('startsAt', 'N/A'))}"""
            
        elif alert_type == 'memory':
            content = f"""{config['emoji']} **ALERTA DE {config['name']}** {severity_config['emoji']}

**Nível:** `{severity_config['label']}`
**Servidor:** `{real_ip if real_ip else clean_host}`
**Prometheus:** `{prometheus_source}`
**Uso atual:** `{metric_value:.1f}{config['unit']}`

**Descrição:** {description}
**Status:** {alert_status.upper()}
**Hora:** {format_timestamp(alert_data.get('startsAt', 'N/A'))}"""
            
        elif alert_type == 'container':
            container_status = "🟢 RODANDO" if metric_value == 1 else "🔴 PARADO"
            container_info = enriched_info.get('container_context', {})
            content = f"""{config['emoji']} **ALERTA DE {config['name']}** {severity_config['emoji']}

**Status:** `{severity_config['label']}`
**Servidor:** `{real_ip if real_ip else clean_host}`
**Prometheus:** `{prometheus_source}`
**Container:** `{device}`
**Estado:** {container_status}
**Namespace:** `{container_info.get('namespace', 'N/A')}`

**Descrição:** {description}
**Status do Alerta:** {alert_status.upper()}
**Hora:** {format_timestamp(alert_data.get('startsAt', 'N/A'))}"""
            
        else:  # default
            content = f"""{config['emoji']} **ALERTA DE {config['name']}** {severity_config['emoji']}

**Nível:** `{severity_config['label']}`
**Servidor:** `{real_ip if real_ip else clean_host}`
**Prometheus:** `{prometheus_source}`
**Componente:** `{device}`
**Valor:** `{metric_value:.1f}{config['unit']}`

**Descrição:** {description}
**Status:** {alert_status.upper()}
**Hora:** {format_timestamp(alert_data.get('startsAt', 'N/A'))}"""
        
        # Monta embed com cor baseada na severidade
        embed = {
            "color": severity_config['color'],
            "fields": [
                {
                    "name": "📊 Detalhes Técnicos",
                    "value": f"**Alert:** {alertname}\n**Instance:** {labels.get('instance', 'N/A')}\n**Severidade:** {severity_config['label']}",
                    "inline": True
                }
            ]
        }
        
        # Campo de métricas específico por tipo
        if alert_type == 'container':
            container_status = "RODANDO" if metric_value == 1 else "PARADO"
            embed["fields"].append({
                "name": "🐳 Status do Container",
                "value": f"**Estado:** {container_status}\n**Container:** {device}",
                "inline": True
            })
        else:
            # Para CPU, Memória, Disco - mostra percentuais e limites
            threshold_text = "N/A"
            if severity_level in SEVERITY_LEVELS and 'threshold_min' in SEVERITY_LEVELS[severity_level]:
                threshold_text = f"{SEVERITY_LEVELS[severity_level]['threshold_min']}-{SEVERITY_LEVELS[severity_level]['threshold_max']}%"
            
            embed["fields"].append({
                "name": "📈 Métricas",
                "value": f"**Valor:** {metric_value:.1f}{config['unit']}\n**Limite:** {threshold_text}",
                "inline": True
            })
        
        # Adiciona GIF baseado na severidade se configurado
        if severity_config['gif']:
            embed["image"] = {"url": severity_config['gif']}
        
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