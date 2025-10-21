from .constants import SEVERITY_LEVELS


def is_container_alert(labels):
    alertname = labels.get('alertname', '').lower()

    container_indicators = [
        labels.get('container'),
        labels.get('container_name'),
        labels.get('pod'),
        labels.get('pod_name'),
        'container' in labels.get('service_type', '').lower(),
        'docker' in labels.get('service_type', '').lower(),
        'container' in labels.get('job', '').lower(),
        'docker' in labels.get('job', '').lower(),
        'cadvisor' in labels.get('job', '').lower(),
        'kubelet' in labels.get('job', '').lower(),
        labels.get('__name__', '').startswith('container_'),
        'container_up' in labels.get('__name__', ''),
        'up{job=~".*container.*"}' in str(labels),
    ]

    container_alertnames = [
        'container' in alertname,
        'containerdown' in alertname.replace(' ', '').replace('_', '').replace('-', ''),
        'poddown' in alertname.replace(' ', '').replace('_', '').replace('-', ''),
        'dockerdown' in alertname.replace(' ', '').replace('_', '').replace('-', ''),
    ]

    return any(container_indicators) or any(container_alertnames)


def detect_alert_type(labels, annotations, alertname):
    alertname_lower = alertname.lower()
    description_lower = annotations.get('description', '').lower()
    service_type = labels.get('service_type', '').lower()

    if is_container_alert(labels):
        return 'container'

    if 'postgres' in service_type:
        return 'default'
    elif 'container' in service_type or 'docker' in service_type:
        return 'container'
    elif 'node' in service_type:
        if 'device' in labels or any(keyword in alertname_lower for keyword in ['disk', 'storage', 'filesystem']):
            return 'disk'
        elif any(keyword in alertname_lower for keyword in ['memory', 'mem', 'ram']):
            return 'memory'
        elif any(keyword in alertname_lower for keyword in ['cpu', 'processor', 'load']):
            return 'cpu'

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
    elif any(keyword in description_lower for keyword in ['container', 'docker', 'pod']):
        return 'container'

    return 'default'


def get_severity_level(metric_value, alert_type="default"):
    if alert_type == "container":
        if metric_value == 0 or metric_value == 0.0:
            return "container_down"
        else:
            return "container_up"

    if metric_value < 80:
        return "low"
    elif 80 <= metric_value < 90:
        return "medium"
    else:
        return "high"


def get_severity_config(severity_level, alert_type="default"):
    level_config = SEVERITY_LEVELS.get(severity_level)
    if level_config:
        color = level_config.get("colors", {}).get(alert_type) if "colors" in level_config else level_config.get("color")
        gif = level_config.get("gifs", {}).get(alert_type) if "gifs" in level_config else level_config.get("gif")
        return {
            "emoji": level_config.get("emoji", ""),
            "label": level_config.get("label", severity_level.upper()),
            "color": color,
            "gif": gif,
        }

    # fallback para níveis percentuais
    percent_level = SEVERITY_LEVELS.get("low")
    return {
        "emoji": percent_level["emoji"],
        "label": percent_level["label"],
        "color": percent_level["colors"].get(alert_type, percent_level["colors"]["default"]),
        "gif": percent_level["gifs"].get(alert_type, percent_level["gifs"]["default"]),
    }
