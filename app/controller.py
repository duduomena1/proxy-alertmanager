from flask import Flask, request
import os
import json

from .constants import ALERT_CONFIGS, APP_PORT, DEBUG_MODE, SEVERITY_LEVELS, ALERT_DEDUP_ENABLED, ALERT_COOLDOWN_SECONDS, ALERT_CACHE_MAX
from .constants import CONTAINER_ALWAYS_NOTIFY_ALLOWLIST
from .constants import CONTAINER_SUPPRESS_REPEATS
from .dedupe import TTLCache, build_alert_fingerprint
from .utils import format_timestamp, extract_metric_value_enhanced, format_metric_value, _is_meaningful
from .enrichment import extract_real_ip_and_source, build_server_location
from .detection import detect_alert_type, get_severity_level, get_severity_config, is_container_alert
from .formatters import extract_container_info, format_container_alert
from .portainer import portainer_client
from .portainer_monitor import start_portainer_monitor
from .services import send_discord_payload
from .suppression import ContainerSuppressor, compute_state, build_container_key


def create_app():
    app = Flask(__name__)
    # Cache de dedupe (em memória, por processo)
    dedupe_cache = TTLCache(ttl_seconds=ALERT_COOLDOWN_SECONDS, max_size=ALERT_CACHE_MAX)
    # Supressor de repetição (por container)
    container_suppressor = ContainerSuppressor()

    @app.route('/health', methods=['GET'])
    def health():
        return {'status': 'ok', 'service': 'grafana-discord-proxy'}, 200

    @app.route('/alert', methods=['POST'])
    def alert():
        try:
            data = request.json
            if DEBUG_MODE:
                print(f"[DEBUG] Received data: {data}")

            if 'alerts' in data and len(data['alerts']) > 0:
                return handle_grafana_alert(data)

            return handle_legacy_alert(data)
        except Exception as e:
            if DEBUG_MODE:
                print(f"[ERROR] {str(e)}")
            return f'Error: {str(e)}', 500

    # Inicia monitoramento ativo via Portainer (se habilitado)
    try:
        start_portainer_monitor(dedupe_cache)
    except Exception as exc:
        if DEBUG_MODE:
            print(f"[DEBUG] Falha ao iniciar PortainerMonitor: {exc}")

    @app.route('/alert_minimal', methods=['POST'])
    def alert_minimal():
        try:
            if request.is_json:
                data = request.json
                text_content = data.get('message', str(data))
            else:
                text_content = request.get_data(as_text=True)

            if DEBUG_MODE:
                print(f"[DEBUG] Received minimal template data: {repr(text_content[:500])}...")

            alerts = parse_minimal_template_data(text_content)

            if alerts:
                if DEBUG_MODE:
                    print(f"[DEBUG] Processados {len(alerts)} alertas dos templates minimalistas")
                    for alert in alerts:
                        print(f"[DEBUG] - {alert['alert_type']}: {alert['host_info']['ip']} = {alert['metric_value']}")

                message = format_enhanced_alert_message(alerts)
                resp = send_discord_payload(content=message)
                return '', resp.status_code
            else:
                resp = send_discord_payload(content=f"📢 **ALERTA RECEBIDO**\n```\n{text_content}\n```")
                return '', resp.status_code

        except Exception as e:
            if DEBUG_MODE:
                print(f"[DEBUG] Erro ao processar template minimal: {e}")

            resp = send_discord_payload(content=f"⚠️ **ALERTA** (processamento simplificado)\n```\n{request.get_data(as_text=True)}\n```")
            return '', resp.status_code

    def enrich_alert_data(alert_data):
        for alert in alert_data.get('alerts', []):
            labels = alert.get('labels', {})
            ip_info = extract_real_ip_and_source(labels)
            alert['enriched_data'] = {
                'real_ip': ip_info['real_ip'],
                'prometheus_source': ip_info['prometheus_source'],
                'original_instance': ip_info['original_instance'],
                'clean_host': ip_info['clean_host'],
                'timestamp_processed': os.getenv('TIMESTAMP', ''),
            }
            if is_container_alert(labels):
                alert['enriched_data']['container_context'] = extract_container_info(labels)
        return alert_data

    def get_metric_value(values, value_string=None, alert_type="default", debug_mode=False):
        return extract_metric_value_enhanced(values, value_string, alert_type, debug_mode)

    def build_portainer_embed_value(result):
        if not result or not result.get('enabled'):
            return None

        if result.get('verified'):
            running = result.get('running')
            status_raw = (result.get('status') or ('running' if running else 'unknown')).lower()
            if status_raw in ['missing', 'exited', 'dead', 'created', 'paused']:
                status = 'stopped'
            elif running:
                status = 'running'
            else:
                status = status_raw
            emoji = "🟢" if running else "🔴"
            lines = [f"{emoji} Estado: `{status}`"]

            health = result.get('health')
            if health:
                lines.append(f"🩺 Health: `{health}`")

            matched = result.get('matched_name')
            if matched:
                lines.append(f"📛 Nome: `{matched}`")

            return "\n".join(lines)

        reason = result.get('error') or 'não verificado'
        return f"ℹ️ {reason}"

    def handle_grafana_alert(data):
        enriched_data = enrich_alert_data(data)
        processed_alerts = []

        for alert_data in enriched_data['alerts']:
            labels = alert_data.get('labels', {})
            annotations = alert_data.get('annotations', {})
            values = alert_data.get('values', {})
            value_string = alert_data.get('valueString', '')
            enriched_info = alert_data.get('enriched_data', {})

            alertname = labels.get('alertname', 'Alerta')
            alert_type = detect_alert_type(labels, annotations, alertname)
            config = ALERT_CONFIGS.get(alert_type, ALERT_CONFIGS['default'])

            real_ip = enriched_info.get('real_ip')
            clean_host = enriched_info.get('clean_host', 'unknown')
            device = labels.get('device', labels.get('container', labels.get('job', 'N/A')))
            mountpoint = labels.get('mountpoint', '/')

            debug_enabled = os.getenv("DEBUG_MODE", "False").lower() == "true"
            metric_value = get_metric_value(values, value_string, alert_type, debug_enabled)

            description = annotations.get('description', '').replace('"', '').strip() or annotations.get('summary', 'Sem descrição disponível')
            alert_status = alert_data.get('status', 'unknown')
            is_firing = alert_status == 'firing'

            if is_firing:
                severity_level = get_severity_level(metric_value, alert_type)
            else:
                severity_level = "resolved"

            severity_config = get_severity_config(severity_level, alert_type)

            location_info = build_server_location(enriched_info, labels)
            server_display = location_info.get('display')
            prometheus_display = location_info.get('prometheus')
            value_text = format_metric_value(metric_value, config['unit'])

            portainer_result = None

            if alert_type == 'container':
                if portainer_client.enabled:
                    host_for_portainer = real_ip if real_ip and real_ip != 'unknown' else clean_host
                    if not host_for_portainer or host_for_portainer == 'unknown':
                        host_for_portainer = None
                    try:
                        portainer_result = portainer_client.verify_container(host_for_portainer, labels)
                    except Exception as exc:
                        if DEBUG_MODE:
                            print(f"[DEBUG] Falha ao consultar Portainer: {exc}")
                        portainer_result = portainer_client.verify_container(None, labels)
                        portainer_result['error'] = f'exception:{exc}'

                content = format_container_alert(
                    alert_data,
                    enriched_info,
                    labels,
                    values,
                    alert_status,
                    description,
                    severity_config,
                    get_metric_value,
                    portainer_result=portainer_result,
                )

                # LÓGICA DE SUPRESSÃO POR ESTADO (apenas containers)
                try:
                    current_state = compute_state(portainer_result, metric_value, alert_status)
                    container_info = alert_data.get('enriched_data', {}).get('container_context', {})
                    container_name = container_info.get('container_name') or labels.get('container') or labels.get('container_name')
                    host_key = real_ip or clean_host
                    key = build_container_key(host_key, labels)
                    
                    # Resolver endpoint_id para verificação blue/green
                    endpoint_id = None
                    if portainer_client.enabled and portainer_result:
                        host_for_endpoint = real_ip if real_ip and real_ip != 'unknown' else clean_host
                        if host_for_endpoint and host_for_endpoint != 'unknown':
                            endpoint_id = portainer_client.resolve_endpoint(host_for_endpoint)
                    
                    should_send, reason = container_suppressor.should_send(
                        key, current_state, 
                        container_name=container_name,
                        portainer_client=portainer_client if portainer_client.enabled else None,
                        endpoint_id=endpoint_id
                    )
                    if DEBUG_MODE:
                        print(f"[DEBUG] Container suppression check: key={key} state={current_state} send={should_send} reason={reason}")
                    if not should_send:
                        # Pula criação de embed para este alerta
                        if DEBUG_MODE:
                            print("[DEBUG] Suprimindo alerta de container por regra de estado.")
                        continue
                except Exception as exc:
                    if DEBUG_MODE:
                        print(f"[DEBUG] Erro na supressão de container: {exc}")

            elif alert_type == 'disk':
                lines = [
                    f"{config['emoji']} **ALERTA DE {config['name']}** {severity_config['emoji']}",
                    "",
                    f"**Nível:** `{severity_config['label']}`",
                ]
                if server_display:
                    lines.append(f"**Servidor:** `{server_display}`")
                if prometheus_display:
                    lines.append(f"**Prometheus:** `{prometheus_display}`")
                if _is_meaningful(device):
                    lines.append(f"**Dispositivo:** `{device}`")
                if _is_meaningful(mountpoint):
                    lines.append(f"**Ponto de montagem:** `{mountpoint}`")
                lines.append(f"**Uso atual:** `{value_text}`")
                lines.extend([
                    "",
                    f"**Descrição:** {description}",
                    f"**Status:** {alert_status.upper()}",
                    f"**Hora:** {format_timestamp(alert_data.get('startsAt', 'N/A'))}",
                ])
                content = "\n".join(lines)

            elif alert_type == 'cpu':
                lines = [
                    f"{config['emoji']} **ALERTA DE {config['name']}** {severity_config['emoji']}",
                    "",
                    f"**Nível:** `{severity_config['label']}`",
                ]
                if server_display:
                    lines.append(f"**Servidor:** `{server_display}`")
                if prometheus_display:
                    lines.append(f"**Prometheus:** `{prometheus_display}`")
                lines.append(f"**Uso atual:** `{value_text}`")
                lines.extend([
                    "",
                    f"**Descrição:** {description}",
                    f"**Status:** {alert_status.upper()}",
                    f"**Hora:** {format_timestamp(alert_data.get('startsAt', 'N/A'))}",
                ])
                content = "\n".join(lines)

            elif alert_type == 'memory':
                lines = [
                    f"{config['emoji']} **ALERTA DE {config['name']}** {severity_config['emoji']}",
                    "",
                    f"**Nível:** `{severity_config['label']}`",
                ]
                if server_display:
                    lines.append(f"**Servidor:** `{server_display}`")
                if prometheus_display:
                    lines.append(f"**Prometheus:** `{prometheus_display}`")
                lines.append(f"**Uso atual:** `{value_text}`")
                lines.extend([
                    "",
                    f"**Descrição:** {description}",
                    f"**Status:** {alert_status.upper()}",
                    f"**Hora:** {format_timestamp(alert_data.get('startsAt', 'N/A'))}",
                ])
                content = "\n".join(lines)

            else:
                lines = [
                    f"{config['emoji']} **ALERTA DE {config['name']}** {severity_config['emoji']}",
                    "",
                    f"**Nível:** `{severity_config['label']}`",
                ]
                if server_display:
                    lines.append(f"**Servidor:** `{server_display}`")
                if prometheus_display:
                    lines.append(f"**Prometheus:** `{prometheus_display}`")
                if _is_meaningful(device):
                    lines.append(f"**Componente:** `{device}`")
                lines.append(f"**Valor:** `{value_text}`")
                lines.extend([
                    "",
                    f"**Descrição:** {description}",
                    f"**Status:** {alert_status.upper()}",
                    f"**Hora:** {format_timestamp(alert_data.get('startsAt', 'N/A'))}",
                ])
                content = "\n".join(lines)

            embed = {
                "color": severity_config['color'],
                "fields": [
                    {
                        "name": "📊 Detalhes Técnicos",
                        "value": f"**Alert:** {alertname}\n**Instance:** {labels.get('instance', 'N/A')}\n**Severidade:** {severity_config['label']}",
                        "inline": True,
                    }
                ],
            }

            if alert_type == 'container':
                container_info = alert_data.get('enriched_data', {}).get('container_context', {})
                container_name = container_info.get('container_name', device)
                if metric_value == 1:
                    container_status = "🟢 ONLINE"
                elif metric_value == 0:
                    container_status = "🔴 OFFLINE"
                else:
                    container_status = f"⚠️ DESCONHECIDO ({metric_value})"

                embed["fields"].append({
                    "name": "🐳 Container Info",
                    "value": f"**Nome:** {container_name}\n**Estado:** {container_status}\n**Tipo:** {container_info.get('instance_type', 'Container')}",
                    "inline": True,
                })

                # Usar IP do endpoint (via mapa) se disponível
                mapped_ip = None
                if portainer_result and portainer_result.get('endpoint_id') is not None:
                    mapped_ip = portainer_client.get_host_for_endpoint(portainer_result.get('endpoint_id'))
                server_location = mapped_ip if mapped_ip else (real_ip if real_ip else clean_host)
                node_info = container_info.get('node', 'N/A')
                embed["fields"].append({
                    "name": "🌐 Localização",
                    "value": f"**Host:** {server_location}\n**Node:** {node_info}\n**Namespace:** {container_info.get('namespace', 'N/A')}",
                    "inline": True,
                })

                portainer_embed_value = build_portainer_embed_value(portainer_result)
                if portainer_embed_value:
                    embed["fields"].append({
                        "name": "🔁 Portainer",
                        "value": portainer_embed_value,
                        "inline": True,
                    })
            else:
                threshold_text = "N/A"
                if severity_level in SEVERITY_LEVELS and 'threshold_min' in SEVERITY_LEVELS[severity_level]:
                    threshold_text = f"{SEVERITY_LEVELS[severity_level]['threshold_min']}-{SEVERITY_LEVELS[severity_level]['threshold_max']}%"

                embed["fields"].append({
                    "name": "📈 Métricas",
                    "value": f"**Valor:** {value_text}\n**Limite:** {threshold_text}",
                    "inline": True,
                })

                host_lines = []
                if server_display:
                    host_lines.append(f"**Host:** {server_display}")
                if prometheus_display:
                    host_lines.append(f"**Prometheus:** {prometheus_display}")
                if host_lines:
                    embed["fields"].append({
                        "name": "🌐 Host",
                        "value": "\n".join(host_lines),
                        "inline": True,
                    })

            if severity_config['gif']:
                embed["image"] = {"url": severity_config['gif']}

            # Flag para evitar dedupe quando no allowlist de "sempre notificar"
            always_notify = False
            if alert_type == 'container':
                cinfo = alert_data.get('enriched_data', {}).get('container_context', {})
                cname = cinfo.get('container_name') or labels.get('container') or labels.get('container_name')
                cname_norm = (cname or '').strip().lower()
                always_notify = cname_norm in {n.strip().lower() for n in CONTAINER_ALWAYS_NOTIFY_ALLOWLIST}

            processed_alerts.append({
                "content": content,
                "embed": embed,
                "type": alert_type,
                "status": alert_status,
                "labels": labels,
                "enriched": enriched_info,
                "always_notify": always_notify,
            })

        for alert in processed_alerts:
            # Dedupe/cooldown: evita reenvio do mesmo alerta por 60m (exceto always_notify)
            if ALERT_DEDUP_ENABLED and not alert.get('always_notify', False):
                fp = build_alert_fingerprint(alert['type'], alert['labels'], alert['enriched'], alert_status=alert['status'])
                if dedupe_cache.is_within_ttl(fp):
                    if DEBUG_MODE:
                        print(f"[DEBUG] DEDUPE: suprimindo alerta duplicado dentro do cooldown: {fp}")
                    continue
                # registra envio
                dedupe_cache.touch(fp)
            payload_embeds = [alert["embed"]]
            if DEBUG_MODE:
                print(f"[DEBUG] Sending {alert['type']} alert payload:")
                print(f"[DEBUG] Content length: {len(alert['content'])}")
                print(f"[DEBUG] Payload: {json.dumps({'content': alert['content'], 'embeds': payload_embeds}, indent=2)[:500]}...")

            resp = send_discord_payload(content=alert["content"], embeds=payload_embeds)
            if DEBUG_MODE:
                print(f"[DEBUG] Sent {alert['type']} alert, status: {resp.status_code}")

        return '', 200

    def handle_legacy_alert(data):
        title = data.get('title', 'Alerta!')
        message = data.get('message', '')
        eval_matches = data.get('evalMatches', [])
        metric_info = ""
        gif_url = data.get('gif', '')

        for match in eval_matches:
            metric = match.get('metric', 'Métrica')
            value = match.get('value', 'N/A')
            tags = match.get('tags', {})
            tagstr = ', '.join([f"{k}: {v}" for k, v in tags.items()])
            metric_info += f"\n**{metric}**: `{value}` {tagstr}"

        payload_embeds = []
        if gif_url:
            payload_embeds.append({"image": {"url": gif_url}})

        resp = send_discord_payload(content=f"🚨 **{title}**\n{message}{metric_info}", embeds=payload_embeds)
        return '', resp.status_code

    # --- Minimal templates parsing/formatting (migrated sem alterações de comportamento) ---
    import re

    def parse_minimal_template_data(text):
        alerts = []
        patterns = [
            r'CPU_ALERT_START(.*?)CPU_ALERT_END',
            r'MEMORY_ALERT_START(.*?)MEMORY_ALERT_END',
            r'CONTAINER_ALERT_START(.*?)CONTAINER_ALERT_END',
            r'DISK_ALERT_START(.*?)DISK_ALERT_END',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            for match in matches:
                alert_data = parse_alert_block(match)
                if alert_data:
                    alerts.append(alert_data)
        return alerts

    def detect_alert_type_from_name(alertname):
        alertname = alertname.lower()
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
        for key in ['host_ip', 'real_host', '__address__', 'instance']:
            if labels.get(key):
                value = labels[key]
                ip_match = re.match(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', value)
                if ip_match:
                    return {'ip': ip_match.group(1), 'raw': value, 'source': key}
                else:
                    return {'ip': value, 'raw': value, 'source': key}
        return {'ip': 'unknown', 'raw': 'unknown', 'source': 'none'}

    def extract_metric_value_minimal(values, valuestring):
        if values:
            for key in ['A', 'B', 'C']:
                if key in values:
                    try:
                        return float(values[key])
                    except Exception:
                        pass
        if valuestring and valuestring != 'unknown':
            number_match = re.search(r'(\d+(?:\.\d+)?)', str(valuestring))
            if number_match:
                try:
                    return float(number_match.group(1))
                except Exception:
                    pass
        return 0.0

    def analyze_container_status(labels, metric_value, alert_status):
        container_name = (
            labels.get('container') or labels.get('container_name') or labels.get('pod') or labels.get('name', 'Container Desconhecido')
        )
        if metric_value == 0:
            if alert_status.lower() == 'firing':
                status_type = "DOWN"; status_icon = "🔴"; status_description = "Container está PARADO e não responde"; severity = "CRÍTICO"
            else:
                status_type = "RECOVERING"; status_icon = "🔄"; status_description = "Container estava parado mas pode estar reiniciando"; severity = "ATENÇÃO"
        elif metric_value == 1:
            status_type = "UP"; status_icon = "🟢"; status_description = "Container está funcionando normalmente"; severity = "OK"
        else:
            status_type = "UNKNOWN"; status_icon = "❓"; status_description = f"Status desconhecido (valor: {metric_value})"; severity = "DESCONHECIDO"

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
            'should_alert': status_type in ['DOWN', 'UNKNOWN'] and alert_status.lower() == 'firing',
        }

    def parse_alert_block(block):
        lines = block.strip().split('\n')
        data = {}
        labels = {}
        values = {}
        for line in lines:
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip(); value = value.strip()
                if not value or value.lower() in ['', 'n/a', 'null', 'none']:
                    continue
                if key in ['alertname', 'status', 'startsAt', 'valuestring']:
                    data[key] = value
                elif key.startswith('value_'):
                    metric_key = key.replace('value_', '')
                    try:
                        values[metric_key] = float(value)
                    except Exception:
                        values[metric_key] = value
                elif key in ['container', 'container_name', 'pod', 'pod_name', 'name', 'namespace', 'image', 'node', 'kubernetes_node']:
                    labels[key] = value
                else:
                    labels[key] = value

        alertname = data.get('alertname', '').lower()
        alert_type = detect_alert_type_from_name(alertname)
        host_info = extract_host_info_minimal(labels)
        metric_value = extract_metric_value_minimal(values, data.get('valuestring', ''))
        return {
            'alert_type': alert_type,
            'alertname': data.get('alertname', 'Unknown Alert'),
            'status': data.get('status', 'unknown'),
            'startsAt': data.get('startsAt', ''),
            'host_info': host_info,
            'metric_value': metric_value,
            'labels': labels,
            'values': values,
            'raw_data': data,
        }

    def format_enhanced_alert_message(alerts):
        if not alerts:
            return "⚠️ **Alerta recebido mas não foi possível processar os dados**"
        message_parts = []
        filtered_alerts = []
        for alert in alerts:
            if alert['alert_type'] == 'container':
                container_analysis = analyze_container_status(alert['labels'], alert['metric_value'], alert['status'])
                if container_analysis['should_alert']:
                    filtered_alerts.append(alert)
                    if DEBUG_MODE:
                        print(f"[DEBUG] Container {container_analysis['status_type']} detectado: {container_analysis['container_name']} = {alert['metric_value']}")
                else:
                    if DEBUG_MODE:
                        print(f"[DEBUG] Container {container_analysis['status_type']} ignorado: {container_analysis['container_name']} = {alert['metric_value']}")
            else:
                filtered_alerts.append(alert)

        if not filtered_alerts:
            return "ℹ️ **Nenhum alerta crítico para processar** (containers UP ou alertas resolvidos ignorados)"

        alerts_by_type = {}
        for alert in filtered_alerts:
            alerts_by_type.setdefault(alert['alert_type'], []).append(alert)

        for alert_type, type_alerts in alerts_by_type.items():
            config = ALERT_CONFIGS.get(alert_type, ALERT_CONFIGS['default'])
            message_parts.append(f"\n{config['emoji']} **ALERTAS DE {config['name'].upper()}**")
            message_parts.append("=" * 50)
            for alert in type_alerts:
                host = alert['host_info']
                labels = alert['labels']
                message_parts.append(f"\n📍 **Servidor:** {host['ip']} (`{host['source']}`)")
                message_parts.append(f"🚨 **Status:** {alert['status'].upper()}")
                if alert_type == 'disk':
                    device = labels.get('device', 'N/A'); mountpoint = labels.get('mountpoint', 'N/A'); fstype = labels.get('fstype', 'N/A')
                    message_parts.append(f"💿 **Dispositivo:** {device}")
                    message_parts.append(f"📁 **Ponto de Montagem:** {mountpoint}")
                    if fstype != 'N/A':
                        message_parts.append(f"🗂️ **Filesystem:** {fstype}")
                    if alert['metric_value'] > 0:
                        message_parts.append(f"📊 **Uso do Disco:** {alert['metric_value']}{config['unit']}")
                elif alert_type == 'container':
                    container_name = labels.get('container') or labels.get('container_name') or labels.get('name') or labels.get('pod') or labels.get('pod_name') or 'Container Desconhecido'
                    if alert['metric_value'] == 0:
                        container_status = "🔴 **CONTAINER PARADO/OFFLINE**"; status_detail = "❌ **CRÍTICO** - Container não está respondendo"
                    elif alert['status'].lower() == 'firing':
                        container_status = "� **CONTAINER COM PROBLEMAS**"; status_detail = "⚠️ **ALERTA** - Container pode estar instável"
                    else:
                        container_status = "❓ **STATUS DESCONHECIDO**"; status_detail = f"ℹ️ Valor da métrica: {alert['metric_value']}"
                    namespace = labels.get('namespace', labels.get('kube_namespace', 'default'))
                    node = labels.get('node', labels.get('kubernetes_node', labels.get('node_name', 'N/A')))
                    image = labels.get('image', labels.get('container_image', 'N/A'))
                    message_parts.append(f"🐳 **Container:** `{container_name}`")
                    message_parts.append(f"{container_status}")
                    if namespace != 'default':
                        message_parts.append(f"📦 **Namespace:** `{namespace}`")
                    if node != 'N/A':
                        message_parts.append(f"🖥️ **Node:** `{node}`")
                    if image != 'N/A':
                        image_name = image.split('/')[-1] if '/' in image else image
                        if len(image_name) > 35:
                            image_name = image_name[:32] + "..."
                        message_parts.append(f"�️ **Image:** `{image_name}`")
                elif alert_type in ['cpu', 'memory']:
                    if alert['metric_value'] > 0:
                        severity = "🔥 CRÍTICO" if alert['metric_value'] >= 90 else "🚧 ALERTA" if alert['metric_value'] >= 80 else "⚠️ ATENÇÃO"
                        message_parts.append(f"📊 **Uso de {config['name']}:** {alert['metric_value']}{config['unit']} ({severity})")
                message_parts.append(f"⏰ **Início:** {alert['startsAt']}")
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

    return app
