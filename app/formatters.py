import json
from .utils import format_timestamp, format_metric_value
from .detection import is_container_alert
from .portainer import portainer_client


def extract_container_info(labels):
    container_name = None
    container_sources = [
        labels.get('container'),
        labels.get('container_name'),
        labels.get('pod'),
        labels.get('pod_name'),
        labels.get('name'),
        labels.get('id'),
    ]
    for source in container_sources:
        if source and source != 'POD' and source not in ['', 'N/A']:
            container_name = source
            break
    if not container_name:
        job = labels.get('job', '')
        if 'container' in job.lower():
            container_name = job

    namespace = labels.get('namespace', labels.get('kube_namespace', 'default'))
    node = labels.get('node', labels.get('kubernetes_node', labels.get('node_name')))
    service = labels.get('service', labels.get('kubernetes_service'))
    image = labels.get('image', labels.get('container_image'))

    return {
        'container_name': container_name or 'Container Desconhecido',
        'namespace': namespace,
        'pod': labels.get('pod'),
        'service': service,
        'node': node,
        'image': image,
        'job': labels.get('job'),
        'instance_type': 'Kubernetes Pod' if labels.get('pod') else 'Docker Container',
    }


def validate_container_alert_data(alert_data, enriched_info, labels, get_metric_value):
    container_info = enriched_info.get('container_context', {})

    validation_errors = []
    warnings = []

    if not container_info.get('container_name') or container_info.get('container_name') == 'Container Desconhecido':
        warnings.append("Nome do container não identificado claramente")

    real_ip = enriched_info.get('real_ip')
    if not real_ip or real_ip == 'unknown':
        warnings.append("IP do servidor não identificado")

    values = alert_data.get('values', {})
    metric_value = get_metric_value(values, alert_data.get('valueString', ''), 'container', True)
    if metric_value is not None and metric_value not in [0, 1] and metric_value not in [0.0, 1.0]:
        validation_errors.append(f"Valor de métrica inválido para container: {metric_value}")

    if not is_container_alert(labels):
        validation_errors.append("Alerta classificado como container mas não possui indicadores de container")

    return {
        'is_valid': len(validation_errors) == 0,
        'errors': validation_errors,
        'warnings': warnings,
        'container_info': container_info,
        'metric_value': metric_value,
    }


def format_container_alert(alert_data, enriched_info, labels, values, alert_status, description, severity_config, get_metric_value, portainer_result=None):
    validation_result = validate_container_alert_data(alert_data, enriched_info, labels, get_metric_value)

    real_ip = enriched_info.get('real_ip')
    clean_host = enriched_info.get('clean_host', 'unknown')
    prometheus_source = enriched_info.get('prometheus_source', 'unknown')

    if not validation_result['is_valid']:
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
    # Se não identificamos via labels, use o nome detectado pelo Portainer
    if container_name in [None, '', 'Container Desconhecido'] and portainer_result and portainer_result.get('matched_name'):
        container_name = portainer_result.get('matched_name')
    validated_metric_value = validation_result['metric_value']

    if validated_metric_value == 0:
        container_status = "🔴 **OFFLINE/PARADO**"
        status_icon = "🚨"
    elif validated_metric_value == 1:
        container_status = "🟢 **ONLINE/RODANDO**"
        status_icon = "✅"
    else:
        container_status = "⚠️ **STATUS DESCONHECIDO**"
        status_icon = "⚠️"

    # Preferir IP do endpoint do Portainer, se disponível no mapa
    server_ip = None
    if portainer_result and portainer_result.get('endpoint_id') is not None:
        mapped = portainer_client.get_host_for_endpoint(portainer_result.get('endpoint_id'))
        if mapped:
            server_ip = mapped
    
    # Prioridade: server_ip do Portainer > real_ip > clean_host (que já tem fallback para instance)
    # Garante que sempre teremos um IP para exibir
    display_ip = server_ip or real_ip or clean_host or labels.get('instance', 'IP não identificado')
    if display_ip and ':' in str(display_ip):
        display_ip = display_ip.split(':')[0]  # Remove porta se houver
    
    server_info = f"`{display_ip}`"
    if container_info.get('node'):
        server_info += f" (Node: `{container_info.get('node')}`)"

    warning_section = ""
    if validation_result['warnings']:
        warning_section = f"\n**⚠️ AVISOS:** {'; '.join(validation_result['warnings'])}\n"

    portainer_section = ""
    if portainer_result and portainer_result.get('enabled'):
        if portainer_result.get('verified'):
            running = portainer_result.get('running')
            status_raw = (portainer_result.get('status') or ('running' if running else 'unknown')).lower()
            # Normaliza estados: 'missing' e 'exited' -> 'stopped'
            if status_raw in ['missing', 'exited', 'dead', 'created', 'paused']:
                status = 'stopped'
            elif running:
                status = 'running'
            else:
                status = status_raw
            emoji = "🟢" if running else "🔴"
            lines = [f"{emoji} Estado: `{status}`"]
            health = portainer_result.get('health')
            if health:
                lines.append(f"🩺 Health: `{health}`")
            matched = portainer_result.get('matched_name')
            if matched:
                lines.append(f"📛 Identificado como: `{matched}`")
            portainer_section = "\n" + "\n".join(lines)
        else:
            reason = portainer_result.get('error') or 'não verificado'
            portainer_section = f"\n**ℹ️ Portainer:** `{reason}`"

    parts = [f"{status_icon} **ALERTA DE CONTAINER** {severity_config['emoji']}"]

    # Identificação
    parts.append("\n**🏷️ IDENTIFICAÇÃO**")
    parts.append(f"**Container:** `{container_name}`")
    parts.append(f"**Servidor/Host:** {server_info}")
    
    # Adiciona o campo de instância original para referência
    original_instance = enriched_info.get('original_instance')
    if original_instance and original_instance != display_ip and original_instance not in ['N/A', 'unknown']:
        parts.append(f"**Instância:** `{original_instance}`")
    
    parts.append(f"**Prometheus:** `{prometheus_source}`{portainer_section}")

    # STATUS ATUAL: só se houver namespace
    ns = container_info.get('namespace')
    if ns and ns not in ['N/A', '', None]:
        parts.append("\n**📊 STATUS ATUAL**")
        parts.append(f"**Estado:** {container_status}")
        parts.append(f"**Tipo:** `{container_info.get('instance_type', 'Container')}`")
        parts.append(f"**Namespace:** `{ns}`")

    # DETALHES TÉCNICOS: somente se houver pelo menos um campo útil
    details_lines = []
    if container_info.get('job'):
        details_lines.append(f"**Job:** `{container_info.get('job')}`")
    if container_info.get('service'):
        details_lines.append(f"**Service:** `{container_info.get('service')}`")
    if container_info.get('image'):
        details_lines.append(f"**Image:** `{container_info.get('image')}`")
    if details_lines:
        parts.append("\n**🔍 DETALHES TÉCNICOS**")
        parts.extend(details_lines)
    if warning_section:
        parts.append(warning_section)

    # INFORMAÇÕES DO ALERTA
    parts.append("\n**📝 INFORMAÇÕES DO ALERTA**")
    parts.append(f"**Descrição:** {description}")
    parts.append(f"**Status do Alerta:** `{alert_status.upper()}`")
    parts.append(f"**Timestamp:** `{format_timestamp(alert_data.get('startsAt', 'N/A'))}`")

    return "\n".join(parts)
