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
    """Extrai IP real e fonte do Prometheus usando múltiplas estratégias melhoradas"""
    
    real_ip = None
    prometheus_source = "unknown"
    original_instance = labels.get('instance', 'N/A')
    
    # 1. Identificar fonte do Prometheus (incluindo novas tags e fallbacks)
    prometheus_candidates = [
        labels.get('prometheus_server'),
        labels.get('prometheus'),
        labels.get('prometheus_replica'),
        labels.get('receive'),
        labels.get('exported_job'),  # Fallback adicional
        labels.get('job', '').replace('-exporter', '').replace('node', 'prometheus').replace('cadvisor', 'prometheus'),
        "prometheus-main"  # Fallback padrão
    ]
    
    for candidate in prometheus_candidates:
        if candidate and candidate not in ['', 'N/A', 'unknown']:
            prometheus_source = candidate
            break
    
    # 2. Buscar IP real em ordem de prioridade (melhorado)
    ip_candidates = [
        labels.get('host_ip'),            # Nova tag do Prometheus atualizado
        labels.get('real_host'),          # Nova tag do Prometheus atualizado  
        labels.get('__address__'),        # IP original antes do relabeling
        labels.get('instance'),           # Instance atual
        labels.get('kubernetes_node'),    # Node do K8s
        labels.get('node_name'),          # Nome do node
        labels.get('host'),               # Host label
        labels.get('hostname'),           # Hostname
        labels.get('target'),             # Target do scrape
        labels.get('exported_instance'),  # Instance exportada
        labels.get('server_name')         # Nome do servidor
    ]
    
    for candidate in ip_candidates:
        if candidate and candidate not in ['N/A', '', 'localhost', '127.0.0.1']:
            # Extrair IP se estiver no formato IP:porta
            ip_match = re.match(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', str(candidate))
            if ip_match:
                real_ip = ip_match.group(1)
                break
            # Se não é IP, mas é um hostname válido, mantém (mas remove porta)
            elif ':' in str(candidate) and not candidate.startswith('node-exporter'):
                # Remove porta se houver
                potential_ip = candidate.split(':')[0]
                # Verifica se é um IP válido
                if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', potential_ip):
                    real_ip = potential_ip
                    break
                # Ou se é um hostname válido
                elif len(potential_ip) > 3 and not potential_ip.startswith('node'):
                    real_ip = potential_ip
                    break
    
    return {
        'real_ip': real_ip,
        'prometheus_source': prometheus_source,
        'original_instance': original_instance,
        'clean_host': real_ip if real_ip else original_instance.split(':')[0] if ':' in original_instance else original_instance
    }

def extract_metric_value_enhanced(values, value_string, alert_type="default", debug_mode=False):
    """Extrai valor de métrica com fallback aprimorado e debug específico por tipo"""
    
    if debug_mode:
        print(f"[DEBUG] extract_metric_value_enhanced - Alert Type: {alert_type}")
        print(f"[DEBUG] Values received: {values}")
        print(f"[DEBUG] ValueString received: {value_string}")
    
    extracted_value = None
    extraction_source = None
    
    # Primeiro tenta extrair dos values
    if values and isinstance(values, dict):
        # Prioridade: A, C, B, D, qualquer outro
        for key in ['A', 'C', 'B', 'D']:
            if key in values and values[key] is not None:
                try:
                    extracted_value = float(values[key])
                    extraction_source = f"values[{key}]"
                    if debug_mode:
                        print(f"[DEBUG] Extracted {extracted_value} from {extraction_source}")
                    break
                except (ValueError, TypeError) as e:
                    if debug_mode:
                        print(f"[DEBUG] Failed to convert values[{key}]={values[key]}: {e}")
                    continue
        
        # Se não encontrou nas chaves prioritárias, pega qualquer valor válido
        if extracted_value is None:
            for key, value in values.items():
                if value is not None:
                    try:
                        extracted_value = float(value)
                        extraction_source = f"values[{key}]"
                        if debug_mode:
                            print(f"[DEBUG] Extracted {extracted_value} from fallback {extraction_source}")
                        break
                    except (ValueError, TypeError) as e:
                        if debug_mode:
                            print(f"[DEBUG] Failed to convert values[{key}]={value}: {e}")
                        continue
    
    # Fallback: extrair do valueString
    if extracted_value is None and value_string:
        try:
            # Padrão específico do Grafana: "value=16.002551672152055"
            value_match = re.search(r'value=([0-9]*\.?[0-9]+)', str(value_string))
            if value_match:
                extracted_value = float(value_match.group(1))
                extraction_source = "valueString(value=pattern)"
                if debug_mode:
                    print(f"[DEBUG] Extracted {extracted_value} from {extraction_source}")
            else:
                # Fallback: qualquer número decimal
                number_match = re.search(r'([0-9]*\.?[0-9]+)', str(value_string))
                if number_match:
                    extracted_value = float(number_match.group(1))
                    extraction_source = "valueString(number_pattern)"
                    if debug_mode:
                        print(f"[DEBUG] Extracted {extracted_value} from {extraction_source}")
                        
        except (ValueError, AttributeError) as e:
            if debug_mode:
                print(f"[DEBUG] Failed to extract from valueString: {e}")
    
    # Se ainda não encontrou, retorna 0
    if extracted_value is None:
        extracted_value = 0.0
        extraction_source = "default_fallback"
        if debug_mode:
            print(f"[DEBUG] No value found, using default: {extracted_value}")
    
    # Tratamento específico por tipo de alerta
    if alert_type in ['cpu', 'memory', 'disk']:
        # Para CPU, memória e disco, valores devem estar entre 0-100%
        if extracted_value > 1 and extracted_value <= 100:
            # Valor já está em percentual
            pass
        elif extracted_value > 0 and extracted_value <= 1:
            # Valor está em fração (0-1), converte para percentual
            extracted_value = extracted_value * 100
            if debug_mode:
                print(f"[DEBUG] Converted fraction to percentage: {extracted_value}%")
        elif extracted_value > 100:
            # Valor pode estar em uma escala diferente, tenta normalizar
            if debug_mode:
                print(f"[DEBUG] Value > 100%, might need normalization: {extracted_value}")
    
    if debug_mode:
        print(f"[DEBUG] Final extracted value: {extracted_value} from {extraction_source}")
    
    return extracted_value

def extract_container_info(labels):
    """Extrai informações específicas de containers de forma mais robusta"""
    
    # Extrai nome do container de múltiplas fontes possíveis
    container_name = None
    container_sources = [
        labels.get('container'),
        labels.get('container_name'),
        labels.get('pod'),
        labels.get('pod_name'),
        labels.get('name'),
        labels.get('id'),  # Container ID
    ]
    
    for source in container_sources:
        if source and source != 'POD' and source not in ['', 'N/A']:
            container_name = source
            break
    
    # Se não encontrou, tenta extrair do job
    if not container_name:
        job = labels.get('job', '')
        if 'container' in job.lower():
            container_name = job
    
    # Extrai informações do ambiente (Kubernetes, Docker, etc.)
    namespace = labels.get('namespace', labels.get('kube_namespace', 'default'))
    node = labels.get('node', labels.get('kubernetes_node', labels.get('node_name')))
    service = labels.get('service', labels.get('kubernetes_service'))
    
    # Informações específicas do container
    image = labels.get('image', labels.get('container_image'))
    
    return {
        'container_name': container_name or 'Container Desconhecido',
        'namespace': namespace,
        'pod': labels.get('pod'),
        'service': service,
        'node': node,
        'image': image,
        'job': labels.get('job'),
        'instance_type': 'Kubernetes Pod' if labels.get('pod') else 'Docker Container'
    }

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
            alert['enriched_data']['container_context'] = extract_container_info(labels)
    
    return alert_data

def is_container_alert(labels):
    """Verifica se é um alerta relacionado a container com critérios mais específicos"""
    
    # Critérios específicos para containers
    container_indicators = [
        # Labels diretos de container
        labels.get('container'),
        labels.get('container_name'),
        labels.get('pod'),
        labels.get('pod_name'),
        
        # Service types específicos
        'container' in labels.get('service_type', '').lower(),
        'docker' in labels.get('service_type', '').lower(),
        
        # Job names que indicam containers
        'container' in labels.get('job', '').lower(),
        'docker' in labels.get('job', '').lower(),
        'cadvisor' in labels.get('job', '').lower(),
        'kubelet' in labels.get('job', '').lower(),
        
        # Métricas típicas de containers
        labels.get('__name__', '').startswith('container_'),
        'container_up' in labels.get('__name__', ''),
        'up{job=~".*container.*"}' in str(labels),
    ]
    
    # Verifica alertnames específicos de containers
    alertname = labels.get('alertname', '').lower()
    container_alertnames = [
        'container' in alertname,
        'containerdown' in alertname.replace(' ', '').replace('_', '').replace('-', ''),
        'poddown' in alertname.replace(' ', '').replace('_', '').replace('-', ''),
        'dockerdown' in alertname.replace(' ', '').replace('_', '').replace('-', ''),
    ]
    
    return any(container_indicators) or any(container_alertnames)

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
    """Detecta o tipo de alerta baseado nos dados recebidos com maior precisão"""
    alertname_lower = alertname.lower()
    description_lower = annotations.get('description', '').lower()
    service_type = labels.get('service_type', '').lower()
    
    # Prioridade 1: Usa a função específica para containers primeiro
    if is_container_alert(labels):
        return 'container'
    
    # Prioridade 2: Verifica pelo service_type do Prometheus
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
    
    # Prioridade 3: Verifica por palavras-chave específicas no alertname
    if any(keyword in alertname_lower for keyword in ['cpu', 'processor', 'load']):
        return 'cpu'
    elif any(keyword in alertname_lower for keyword in ['memory', 'mem', 'ram']):
        return 'memory'
    elif any(keyword in alertname_lower for keyword in ['disk', 'storage', 'filesystem']) or 'device' in labels:
        return 'disk'
    elif any(keyword in alertname_lower for keyword in ['container', 'docker', 'pod']):
        return 'container'
    
    # Prioridade 4: Verifica na descrição
    elif 'cpu' in description_lower:
        return 'cpu'
    elif any(keyword in description_lower for keyword in ['memory', 'mem', 'ram']):
        return 'memory'
    elif any(keyword in description_lower for keyword in ['disk', 'disco']):
        return 'disk'
    elif any(keyword in description_lower for keyword in ['container', 'docker', 'pod']):
        return 'container'
    
    return 'default'

def validate_container_alert_data(alert_data, enriched_info, labels):
    """Valida e sanitiza dados de alertas de container para maior segurança"""
    
    container_info = enriched_info.get('container_context', {})
    
    # Validações críticas
    validation_errors = []
    warnings = []
    
    # 1. Verifica se temos informações mínimas necessárias
    if not container_info.get('container_name') or container_info.get('container_name') == 'Container Desconhecido':
        warnings.append("Nome do container não identificado claramente")
    
    # 2. Verifica se o IP foi extraído corretamente
    real_ip = enriched_info.get('real_ip')
    if not real_ip or real_ip == 'unknown':
        warnings.append("IP do servidor não identificado")
    
    # 3. Verifica se a métrica faz sentido para containers
    values = alert_data.get('values', {})
    metric_value = get_metric_value(values, alert_data.get('valueString', ''), 'container', True)
    
    if metric_value not in [0, 1] and metric_value not in [0.0, 1.0]:
        validation_errors.append(f"Valor de métrica inválido para container: {metric_value}")
    
    # 4. Verifica se o alerta realmente é de container
    if not is_container_alert(labels):
        validation_errors.append("Alerta classificado como container mas não possui indicadores de container")
    
    return {
        'is_valid': len(validation_errors) == 0,
        'errors': validation_errors,
        'warnings': warnings,
        'container_info': container_info,
        'metric_value': metric_value
    }

def format_container_alert(alert_data, enriched_info, labels, values, alert_status, description, severity_config):
    """Formata alerta de container com validações de segurança"""
    
    # VALIDAÇÃO DE SEGURANÇA PARA CONTAINERS
    validation_result = validate_container_alert_data(alert_data, enriched_info, labels)
    
    real_ip = enriched_info.get('real_ip')
    clean_host = enriched_info.get('clean_host', 'unknown')
    prometheus_source = enriched_info.get('prometheus_source', 'unknown')
    
    if not validation_result['is_valid']:
        # Se houver erros críticos, trata como alerta padrão com aviso
        error_msg = "; ".join(validation_result['errors'])
        return f"""⚠️ **ALERTA DE CONTAINER - VALIDAÇÃO FALHOU**

**❌ ERROS DE VALIDAÇÃO:** {error_msg}
**Servidor:** `{real_ip if real_ip else clean_host}`
**Descrição Original:** {description}
**Status:** {alert_status.upper()}

**ℹ️ Dados brutos disponíveis para debug:**
```
Labels: {json.dumps(labels, indent=2)}
Values: {json.dumps(values, indent=2)}
```"""
    
    container_info = validation_result['container_info']
    container_name = container_info.get('container_name', 'Container Desconhecido')
    validated_metric_value = validation_result['metric_value']
    
    # Determina status mais preciso
    if validated_metric_value == 0:
        container_status = "🔴 **OFFLINE/PARADO**"
        status_icon = "🚨"
    elif validated_metric_value == 1:
        container_status = "🟢 **ONLINE/RODANDO**"
        status_icon = "✅"
    else:
        container_status = f"⚠️ **STATUS DESCONHECIDO** (valor: {validated_metric_value})"
        status_icon = "⚠️"
    
    # Informações de localização mais claras
    server_info = f"`{real_ip}`" if real_ip else f"`{clean_host}`"
    if container_info.get('node'):
        server_info += f" (Node: `{container_info.get('node')}`)"
    
    # Adiciona warnings se houver
    warning_section = ""
    if validation_result['warnings']:
        warning_section = f"\n**⚠️ AVISOS:** {'; '.join(validation_result['warnings'])}\n"
    
    return f"""{status_icon} **ALERTA DE CONTAINER** {severity_config['emoji']}

**🏷️ IDENTIFICAÇÃO**
**Container:** `{container_name}`
**Servidor/Host:** {server_info}
**Prometheus:** `{prometheus_source}`

**📊 STATUS ATUAL**
**Estado:** {container_status}
**Tipo:** `{container_info.get('instance_type', 'Container')}`
**Namespace:** `{container_info.get('namespace', 'N/A')}`

**🔍 DETALHES TÉCNICOS**
**Job:** `{container_info.get('job', 'N/A')}`
**Service:** `{container_info.get('service', 'N/A')}`
**Image:** `{container_info.get('image', 'N/A')}`{warning_section}

**📝 INFORMAÇÕES DO ALERTA**
**Descrição:** {description}
**Status do Alerta:** `{alert_status.upper()}`
**Timestamp:** `{format_timestamp(alert_data.get('startsAt', 'N/A'))}`"""

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

def get_metric_value(values, value_string=None, alert_type="default", debug_mode=False):
    """Extrai o valor principal da métrica com fallback para valueString"""
    # Usa a função aprimorada com tipo de alerta e debug
    return extract_metric_value_enhanced(values, value_string, alert_type, debug_mode)

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
        
        # EXTRAI valor com fallback aprimorado e debug específico por tipo
        debug_enabled = os.getenv("DEBUG_MODE", "False").lower() == "true"
        metric_value = get_metric_value(values, value_string, alert_type, debug_enabled)
        
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
            # Usa a nova função dedicada para alertas de container
            content = format_container_alert(alert_data, enriched_info, labels, values, alert_status, description, severity_config)
            
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
            container_info = alert_data.get('enriched_data', {}).get('container_context', {})
            container_name = container_info.get('container_name', device)
            container_status = "RODANDO" if metric_value == 1 else "PARADO"
            
            embed["fields"].append({
                "name": "🐳 Container Info",
                "value": f"**Nome:** {container_name}\n**Estado:** {container_status}\n**Tipo:** {container_info.get('instance_type', 'Container')}",
                "inline": True
            })
            
            # Campo adicional com localização
            server_location = real_ip if real_ip else clean_host
            node_info = container_info.get('node', 'N/A')
            embed["fields"].append({
                "name": "🌐 Localização",
                "value": f"**Host:** {server_location}\n**Node:** {node_info}\n**Namespace:** {container_info.get('namespace', 'N/A')}",
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
        
        if DEBUG_MODE:
            print(f"[DEBUG] Sending {alert['type']} alert payload:")
            print(f"[DEBUG] Content length: {len(alert['content'])}")
            print(f"[DEBUG] Payload: {json.dumps(payload, indent=2)[:500]}...")
        
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        if DEBUG_MODE:
            print(f"[DEBUG] Sent {alert['type']} alert, status: {resp.status_code}")
            if resp.status_code != 204:
                print(f"[DEBUG] Response content: {resp.text}")
    
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

def parse_minimal_template_data(text):
    """
    Processa dados dos templates minimalistas que enviam dados brutos
    Procura por blocos ALERT_START/ALERT_END e extrai informações
    """
    alerts = []
    
    # Padrões para diferentes tipos de alertas
    patterns = [
        r'CPU_ALERT_START(.*?)CPU_ALERT_END',
        r'MEMORY_ALERT_START(.*?)MEMORY_ALERT_END', 
        r'CONTAINER_ALERT_START(.*?)CONTAINER_ALERT_END',
        r'DISK_ALERT_START(.*?)DISK_ALERT_END'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            alert_data = parse_alert_block(match)
            if alert_data:
                alerts.append(alert_data)
    
    return alerts

def parse_alert_block(block):
    """
    Extrai dados de um bloco de alerta individual
    """
    lines = block.strip().split('\n')
    data = {}
    labels = {}
    values = {}
    
    if DEBUG_MODE:
        print(f"[DEBUG] parse_alert_block - parsing lines: {lines}")
    
    for line in lines:
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()
            
            if DEBUG_MODE:
                print(f"[DEBUG] Parsing line: '{key}' = '{value}'")
            
            # Remove valores vazios
            if not value or value.lower() in ['', 'n/a', 'null', 'none']:
                continue
            
            # Valores especiais
            if key in ['alertname', 'status', 'startsAt', 'valuestring']:
                data[key] = value
            # Valores de métricas
            elif key.startswith('value_'):
                metric_key = key.replace('value_', '')
                try:
                    values[metric_key] = float(value)
                except:
                    values[metric_key] = value
            # Labels importantes para containers
            elif key in ['container', 'container_name', 'pod', 'pod_name', 'name', 'namespace', 'image', 'node', 'kubernetes_node']:
                labels[key] = value
            # Labels gerais
            else:
                labels[key] = value
    
    # Detecta tipo de alerta
    alertname = data.get('alertname', '').lower()
    alert_type = detect_alert_type_from_name(alertname)
    
    # Extrai IP/Host de forma inteligente
    host_info = extract_host_info_minimal(labels)
    
    # Extrai valor da métrica
    metric_value = extract_metric_value_minimal(values, data.get('valuestring', ''))
    
    # Monta resposta estruturada
    return {
        'alert_type': alert_type,
        'alertname': data.get('alertname', 'Unknown Alert'),
        'status': data.get('status', 'unknown'),
        'startsAt': data.get('startsAt', ''),
        'host_info': host_info,
        'metric_value': metric_value,
        'labels': labels,
        'values': values,
        'raw_data': data
    }

def detect_alert_type_from_name(alertname):
    """
    Detecta tipo de alerta baseado no nome
    """
    alertname = alertname.lower()
    
    # Detecta containers com mais precisão
    container_keywords = ['container', 'docker', 'pod', 'kubelet', 'cadvisor']
    if any(keyword in alertname for keyword in container_keywords):
        return 'container'
    elif 'cpu' in alertname:
        return 'cpu'
    elif 'memory' in alertname or 'memoria' in alertname:
        return 'memory'
    elif 'disk' in alertname or 'disco' in alertname:
        return 'disk'
    else:
        return 'system'

def extract_host_info_minimal(labels):
    """
    Extrai informações do host de forma inteligente para templates minimalistas
    """
    # Ordem de preferência para IP
    for key in ['host_ip', 'real_host', '__address__', 'instance']:
        if labels.get(key):
            value = labels[key]
            # Tenta extrair IP se tiver formato IP:porta
            ip_match = re.match(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', value)
            if ip_match:
                return {
                    'ip': ip_match.group(1),
                    'raw': value,
                    'source': key
                }
            else:
                return {
                    'ip': value,
                    'raw': value,
                    'source': key
                }
    
    return {
        'ip': 'unknown',
        'raw': 'unknown',
        'source': 'none'
    }

def extract_metric_value_minimal(values, valuestring):
    """
    Extrai valor da métrica de diferentes fontes para templates minimalistas
    """
    # Tenta pegar valor do Values primeiro
    if values:
        for key in ['A', 'B', 'C']:  # Ordem comum no Grafana
            if key in values:
                try:
                    return float(values[key])
                except:
                    pass
    
    # Tenta extrair do valuestring
    if valuestring and valuestring != 'unknown':
        # Busca por números na string
        number_match = re.search(r'(\d+(?:\.\d+)?)', str(valuestring))
        if number_match:
            try:
                return float(number_match.group(1))
            except:
                pass
    
    return 0.0

def analyze_container_status(labels, metric_value, alert_status):
    """
    Analisa o status detalhado do container baseado nas informações disponíveis
    """
    container_name = (
        labels.get('container') or 
        labels.get('container_name') or 
        labels.get('pod') or 
        labels.get('name', 'Container Desconhecido')
    )
    
    if DEBUG_MODE:
        print(f"[DEBUG] analyze_container_status: container='{container_name}', value={metric_value}, status='{alert_status}', type={type(metric_value)}")
    
    # Analisa o status baseado no valor da métrica e status do alerta
    if metric_value == 0:
        if alert_status.lower() == 'firing':
            status_type = "DOWN"
            status_icon = "🔴"
            status_description = "Container está PARADO e não responde"
            severity = "CRÍTICO"
        else:
            status_type = "RECOVERING"
            status_icon = "🔄"
            status_description = "Container estava parado mas pode estar reiniciando"
            severity = "ATENÇÃO"
    elif metric_value == 1:
        status_type = "UP"
        status_icon = "🟢"
        status_description = "Container está funcionando normalmente"
        severity = "OK"
    else:
        status_type = "UNKNOWN"
        status_icon = "❓"
        status_description = f"Status desconhecido (valor: {metric_value})"
        severity = "DESCONHECIDO"
    
    # Extrai informações do ambiente
    namespace = labels.get('namespace', labels.get('kube_namespace', 'default'))
    node = labels.get('node', labels.get('kubernetes_node', labels.get('node_name', 'N/A')))
    image = labels.get('image', labels.get('container_image', 'N/A'))
    job = labels.get('job', 'N/A')
    
    return {
        'container_name': container_name,
        'status_type': status_type,
        'status_icon': status_icon,
        'status_description': status_description,
        'severity': severity,
        'namespace': namespace,
        'node': node,
        'image': image,
        'job': job,
        'should_alert': status_type in ['DOWN', 'UNKNOWN'] and alert_status.lower() == 'firing'
    }

def format_enhanced_alert_message(alerts):
    """
    Formata mensagem melhorada com dados processados dos templates minimalistas
    """
    if not alerts:
        return "⚠️ **Alerta recebido mas não foi possível processar os dados**"
    
    message_parts = []
    
    # Filtra alertas - para containers, usa análise inteligente
    filtered_alerts = []
    for alert in alerts:
        if alert['alert_type'] == 'container':
            # Analisa o container para decidir se deve alertar
            container_analysis = analyze_container_status(alert['labels'], alert['metric_value'], alert['status'])
            
            # Só alerta se should_alert for True (container DOWN ou com problemas)
            if container_analysis['should_alert']:
                filtered_alerts.append(alert)
                if DEBUG_MODE:
                    print(f"[DEBUG] Container {container_analysis['status_type']} detectado: {container_analysis['container_name']} = {alert['metric_value']}")
            else:
                if DEBUG_MODE:
                    print(f"[DEBUG] Container {container_analysis['status_type']} ignorado: {container_analysis['container_name']} = {alert['metric_value']}")
        else:
            # Para outros tipos, processa normalmente
            filtered_alerts.append(alert)
    
    if not filtered_alerts:
        return "ℹ️ **Nenhum alerta crítico para processar** (containers UP ou alertas resolvidos ignorados)"
    
    # Agrupa por tipo
    alerts_by_type = {}
    for alert in filtered_alerts:
        alert_type = alert['alert_type']
        if alert_type not in alerts_by_type:
            alerts_by_type[alert_type] = []
        alerts_by_type[alert_type].append(alert)
    
    # Formata cada tipo
    for alert_type, type_alerts in alerts_by_type.items():
        config = ALERT_CONFIGS.get(alert_type, ALERT_CONFIGS['default'])
        
        message_parts.append(f"\n{config['emoji']} **ALERTAS DE {config['name'].upper()}**")
        message_parts.append("=" * 50)
        
        for alert in type_alerts:
            host = alert['host_info']
            labels = alert['labels']
            
            message_parts.append(f"\n📍 **Servidor:** {host['ip']} (`{host['source']}`)")
            message_parts.append(f"🚨 **Status:** {alert['status'].upper()}")
            
            # Informações específicas por tipo de alerta
            if alert_type == 'disk':
                device = labels.get('device', 'N/A')
                mountpoint = labels.get('mountpoint', 'N/A')
                fstype = labels.get('fstype', 'N/A')
                
                message_parts.append(f"💿 **Dispositivo:** {device}")
                message_parts.append(f"📁 **Ponto de Montagem:** {mountpoint}")
                if fstype != 'N/A':
                    message_parts.append(f"🗂️ **Filesystem:** {fstype}")
                    
                if alert['metric_value'] > 0:
                    message_parts.append(f"📊 **Uso do Disco:** {alert['metric_value']}{config['unit']}")
                    
            elif alert_type == 'container':
                # Extrai nome do container de múltiplas fontes
                container_name = (
                    labels.get('container') or 
                    labels.get('container_name') or 
                    labels.get('name') or 
                    labels.get('pod') or 
                    labels.get('pod_name') or
                    'Container Desconhecido'
                )
                
                # Determina status mais detalhado
                if alert['metric_value'] == 0:
                    container_status = "🔴 **CONTAINER PARADO/OFFLINE**"
                    status_detail = "❌ **CRÍTICO** - Container não está respondendo"
                elif alert['status'].lower() == 'firing':
                    container_status = "� **CONTAINER COM PROBLEMAS**" 
                    status_detail = "⚠️ **ALERTA** - Container pode estar instável"
                else:
                    container_status = "❓ **STATUS DESCONHECIDO**"
                    status_detail = f"ℹ️ Valor da métrica: {alert['metric_value']}"
                
                # Informações adicionais do container
                namespace = labels.get('namespace', labels.get('kube_namespace', 'default'))
                pod = labels.get('pod', 'N/A')
                image = labels.get('image', labels.get('container_image', 'N/A'))
                node = labels.get('node', labels.get('kubernetes_node', labels.get('node_name', 'N/A')))
                
                # Usa análise aprimorada de container
                container_analysis = analyze_container_status(labels, alert['metric_value'], alert['status'])
                
                message_parts.append(f"🐳 **Container:** `{container_analysis['container_name']}`")
                message_parts.append(f"{container_analysis['status_icon']} **Status:** {container_analysis['status_description']}")
                message_parts.append(f"� **Severidade:** {container_analysis['severity']}")
                
                # Informações do ambiente - usando dados da análise
                if container_analysis['namespace'] != 'default':
                    message_parts.append(f"📦 **Namespace:** `{container_analysis['namespace']}`")
                if container_analysis['node'] != 'N/A':
                    message_parts.append(f"🖥️ **Node:** `{container_analysis['node']}`")
                if container_analysis['job'] != 'N/A':
                    message_parts.append(f"⚙️ **Job:** `{container_analysis['job']}`")
                
                # Mostra imagem se disponível (versão compacta)
                if container_analysis['image'] != 'N/A':
                    image_name = container_analysis['image'].split('/')[-1] if '/' in container_analysis['image'] else container_analysis['image']
                    if len(image_name) > 35:
                        image_name = image_name[:32] + "..."
                    message_parts.append(f"�️ **Image:** `{image_name}`")
                
            elif alert_type in ['cpu', 'memory']:
                if alert['metric_value'] > 0:
                    severity = "🔥 CRÍTICO" if alert['metric_value'] >= 90 else "🚧 ALERTA" if alert['metric_value'] >= 80 else "⚠️ ATENÇÃO"
                    message_parts.append(f"📊 **Uso de {config['name']}:** {alert['metric_value']}{config['unit']} ({severity})")
            
            message_parts.append(f"⏰ **Início:** {alert['startsAt']}")
            
            # Informações do Prometheus
            prometheus_info = []
            
            if labels.get('prometheus_server'):
                prometheus_info.append(f"Prometheus: {labels['prometheus_server']}")
            if labels.get('job'):
                prometheus_info.append(f"Job: {labels['job']}")
            if labels.get('service_type'):
                prometheus_info.append(f"Service: {labels['service_type']}")
            if labels.get('environment'):
                prometheus_info.append(f"Env: {labels['environment']}")
                
            if prometheus_info:
                message_parts.append(f"🔧 **Config:** {' | '.join(prometheus_info)}")
            
            # Labels importantes que estão chegando (especiais por tipo)
            important_labels = []
            if alert_type == 'disk':
                for key in ['host_ip', 'real_host', 'device', 'mountpoint', 'fstype']:
                    if labels.get(key):
                        important_labels.append(f"{key}: {labels[key]}")
            elif alert_type == 'container':
                for key in ['host_ip', 'real_host', 'container', 'container_name']:
                    if labels.get(key):
                        important_labels.append(f"{key}: {labels[key]}")
            else:
                for key in ['host_ip', 'real_host', 'prometheus_server', 'service_type', 'environment']:
                    if labels.get(key):
                        important_labels.append(f"{key}: {labels[key]}")
            
            if important_labels:
                message_parts.append(f"🏷️ **Labels:** {' | '.join(important_labels[:4])}")
            
            message_parts.append("-" * 30)
    
    return "\n".join(message_parts)

def send_to_discord(message):
    """
    Envia mensagem para o Discord
    """
    payload = {
        "content": message
    }
    
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        if DEBUG_MODE:
            print(f"[DEBUG] Discord response: {resp.status_code}")
        return '', resp.status_code
    except Exception as e:
        if DEBUG_MODE:
            print(f"[DEBUG] Error sending to Discord: {e}")
        return f'Error: {str(e)}', 500

# Adicione nova rota para processar templates minimalistas
@app.route('/alert_minimal', methods=['POST'])
def alert_minimal():
    """
    Endpoint específico para processar alertas dos templates minimalistas
    """
    try:
        # Recebe como texto puro ou JSON
        if request.is_json:
            data = request.json
            text_content = data.get('message', str(data))
        else:
            text_content = request.get_data(as_text=True)
        
        if DEBUG_MODE:
            print(f"[DEBUG] Received minimal template data: {repr(text_content[:500])}...")
        
        # Tenta processar como dados de template minimal
        alerts = parse_minimal_template_data(text_content)
        
        if alerts:
            if DEBUG_MODE:
                print(f"[DEBUG] Processados {len(alerts)} alertas dos templates minimalistas")
                for alert in alerts:
                    print(f"[DEBUG] - {alert['alert_type']}: {alert['host_info']['ip']} = {alert['metric_value']}")
            
            message = format_enhanced_alert_message(alerts)
            return send_to_discord(message)
        else:
            # Fallback para mensagem original
            return send_to_discord(f"📢 **ALERTA RECEBIDO**\n```\n{text_content}\n```")
            
    except Exception as e:
        if DEBUG_MODE:
            print(f"[DEBUG] Erro ao processar template minimal: {e}")
        
        # Fallback
        return send_to_discord(f"⚠️ **ALERTA** (processamento simplificado)\n```\n{request.get_data(as_text=True)}\n```")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=APP_PORT, debug=DEBUG_MODE)