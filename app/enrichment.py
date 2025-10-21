import re
from .utils import pick_first_nonempty, _strip_port


def extract_real_ip_and_source(labels):
    real_ip = None
    prometheus_source = "unknown"
    original_instance = labels.get('instance', 'N/A')

    prometheus_candidates = [
        labels.get('prometheus_server'),
        labels.get('prometheus'),
        labels.get('prometheus_replica'),
        labels.get('receive'),
        labels.get('exported_job'),
        labels.get('job', '').replace('-exporter', '').replace('node', 'prometheus').replace('cadvisor', 'prometheus'),
        "prometheus-main",
    ]

    for candidate in prometheus_candidates:
        if candidate and candidate not in ['', 'N/A', 'unknown']:
            prometheus_source = candidate
            break

    ip_candidates = [
        labels.get('host_ip'),
        labels.get('real_host'),
        labels.get('__address__'),
        labels.get('instance'),
        labels.get('kubernetes_node'),
        labels.get('node_name'),
        labels.get('host'),
        labels.get('hostname'),
        labels.get('target'),
        labels.get('exported_instance'),
        labels.get('server_name'),
    ]

    for candidate in ip_candidates:
        if candidate and candidate not in ['N/A', '', 'localhost', '127.0.0.1']:
            ip_match = re.match(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', str(candidate))
            if ip_match:
                real_ip = ip_match.group(1)
                break
            elif ':' in str(candidate) and not str(candidate).startswith('node-exporter'):
                potential_ip = str(candidate).split(':')[0]
                if re.match(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$', potential_ip):
                    real_ip = potential_ip
                    break
                elif len(potential_ip) > 3 and not potential_ip.startswith('node'):
                    real_ip = potential_ip
                    break

    return {
        'real_ip': real_ip,
        'prometheus_source': prometheus_source,
        'original_instance': original_instance,
        'clean_host': real_ip if real_ip else original_instance.split(':')[0] if ':' in original_instance else original_instance,
    }


def build_server_location(enriched_info, labels):
    real_ip = enriched_info.get('real_ip')
    clean_host = enriched_info.get('clean_host')
    instance = labels.get('instance')
    hostname = labels.get('hostname') or labels.get('host') or labels.get('node_name')
    host_ip = labels.get('host_ip') or labels.get('real_host')

    display = pick_first_nonempty(real_ip, host_ip, clean_host, instance, hostname)
    if display:
        display = _strip_port(display)

    prometheus = pick_first_nonempty(
        enriched_info.get('prometheus_source'),
        labels.get('prometheus_server'),
        labels.get('prometheus'),
        labels.get('prometheus_replica'),
        labels.get('receive'),
    )

    return {
        'display': display,
        'prometheus': prometheus,
    }
