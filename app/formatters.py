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
    if container_name in [None, '', 'Container Desconhecido'] and portainer_result and portainer_result.get('matched_name'):
        container_name = portainer_result.get('matched_name')
    validated_metric_value = validation_result['metric_value']

    from .suppression import extract_blue_green_base
    base_name, color = extract_blue_green_base(container_name) if container_name else (None, None)
    is_blue_green = base_name is not None and color is not None
    
    if validated_metric_value == 0:
        container_status = "🔴 **OFFLINE/PARADO**"
        status_icon = "🚨"
    elif validated_metric_value == 1:
        container_status = "🟢 **ONLINE/RODANDO**"
        status_icon = "✅"
    else:
        container_status = "⚠️ **STATUS DESCONHECIDO**"
        status_icon = "⚠️"

    server_ip = None
    if portainer_result and portainer_result.get('endpoint_id') is not None:
        mapped = portainer_client.get_host_for_endpoint(portainer_result.get('endpoint_id'))
        if mapped:
            server_ip = mapped
    
    display_ip = server_ip or real_ip or clean_host or labels.get('instance', 'IP não identificado')
    if display_ip and ':' in str(display_ip):
        display_ip = display_ip.split(':')[0]
    
    server_info = f"`{display_ip}`"
    node = container_info.get('node')
    if node and node not in [display_ip, real_ip, clean_host, None, 'N/A', '']:
        server_info += f" • Node: `{node}`"

    portainer_section = ""
    if portainer_result and portainer_result.get('enabled'):
        if portainer_result.get('verified'):
            running = portainer_result.get('running')
            status_raw = (portainer_result.get('status') or ('running' if running else 'unknown')).lower()
            if status_raw in ['missing', 'exited', 'dead', 'created', 'paused']:
                status = 'stopped'
            elif running:
                status = 'running'
            else:
                status = status_raw
            emoji = "🟢" if running else "🔴"
            lines = [f"{emoji} Estado: `{status}`"]
            health = portainer_result.get('health')
            if health and health not in ['none', '', None]:
                lines.append(f"🩺 Health: `{health}`")
            matched = portainer_result.get('matched_name')
            if matched and matched.lower() != container_name.lower():
                lines.append(f"📛 Identificado como: `{matched}`")
            portainer_section = "\n" + "\n".join(lines)
        else:
            reason = portainer_result.get('error') or 'não verificado'
            portainer_section = f"\nℹ️ Portainer: `{reason}`"

    if is_blue_green:
        title = f"{status_icon} **ALERTA DE CONTAINER** {severity_config['emoji']} 🔵🟢 Blue/Green"
    else:
        title = f"{status_icon} **ALERTA DE CONTAINER** {severity_config['emoji']}"
    parts = [title]

    parts.append("\n**🏷️ IDENTIFICAÇÃO**")
    if is_blue_green:
        parts.append(f"**Container:** `{container_name}` (Ambiente: `{color.upper()}`)")  
    else:
        parts.append(f"**Container:** `{container_name}`")
    parts.append(f"**Host:** {server_info}")
    
    prometheus_line = f"**Fonte:** `{prometheus_source}`"
    if portainer_result and portainer_result.get('enabled') and portainer_result.get('verified'):
        prometheus_line += f"{portainer_section}"
    parts.append(prometheus_line)

    parts.append("\n**📊 STATUS**")
    parts.append(f"**Estado:** {container_status}")
    
    ns = container_info.get('namespace')
    if ns and ns not in ['N/A', '', None, 'default']:
        parts.append(f"**Namespace:** `{ns}`")
    
    instance_type = container_info.get('instance_type', '')
    if instance_type and 'Kubernetes' in instance_type:
        parts.append(f"**Tipo:** `{instance_type}`")

    details_lines = []
    
    service = container_info.get('service')
    if service and service not in ['', None, 'N/A']:
        details_lines.append(f"**Service:** `{service}`")
    
    image = container_info.get('image')
    if image and image not in ['', None, 'N/A']:
        if len(image) > 60:
            image_parts = image.split('/')
            image = image_parts[-1].split('@')[0].split(':')[0]
        if image:
            details_lines.append(f"**Image:** `{image}`")
    
    if details_lines:
        parts.append("\n**🔍 DETALHES**")
        parts.extend(details_lines)

    parts.append("\n**📝 ALERTA**")
    parts.append(f"**Descrição:** {description}")
    parts.append(f"**Status:** `{alert_status.upper()}` • **Hora:** `{format_timestamp(alert_data.get('startsAt', 'N/A'))}`")

    return "\n".join(parts)
