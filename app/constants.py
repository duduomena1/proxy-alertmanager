import os

# Configurações globais de ambiente
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
APP_PORT = int(os.getenv("APP_PORT", "5001"))
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"

# Dedupe/cooldown de alertas
ALERT_DEDUP_ENABLED = os.getenv("ALERT_DEDUP_ENABLED", "true").lower() == "true"
ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "3600"))  # 60 minutos por padrão
ALERT_CACHE_MAX = int(os.getenv("ALERT_CACHE_MAX", "5000"))

# Integração com Portainer CE
CONTAINER_VALIDATE_WITH_PORTAINER = os.getenv("CONTAINER_VALIDATE_WITH_PORTAINER", "false").lower() == "true"
PORTAINER_BASE_URL = os.getenv("PORTAINER_BASE_URL")
PORTAINER_API_KEY = os.getenv("PORTAINER_API_KEY")
PORTAINER_TIMEOUT_SECONDS = int(os.getenv("PORTAINER_TIMEOUT_SECONDS", "3"))
PORTAINER_VERIFY_TLS = os.getenv("PORTAINER_VERIFY_TLS", "true").lower() == "true"
PORTAINER_FAIL_OPEN = os.getenv("PORTAINER_FAIL_OPEN", "true").lower() == "true"
PORTAINER_ENDPOINT_MAP_FILE = os.getenv("PORTAINER_ENDPOINT_MAP_FILE")
PORTAINER_STRICT_NAME_MATCH = os.getenv("PORTAINER_STRICT_NAME_MATCH", "false").lower() == "true"

# Monitoramento ativo via Portainer (polling)
PORTAINER_ACTIVE_MONITOR = os.getenv("PORTAINER_ACTIVE_MONITOR", "true").lower() == "true"
PORTAINER_MONITOR_INTERVAL_SECONDS = int(os.getenv("PORTAINER_MONITOR_INTERVAL_SECONDS", "30"))
PORTAINER_MONITOR_ENDPOINTS = os.getenv("PORTAINER_MONITOR_ENDPOINTS", "").strip()
PORTAINER_MONITOR_DOWN_CONFIRMATIONS = int(os.getenv("PORTAINER_MONITOR_DOWN_CONFIRMATIONS", "1"))
PORTAINER_MONITOR_SCOPE = os.getenv("PORTAINER_MONITOR_SCOPE", "map").strip().lower()  # 'map' | 'all'
# Se true, PortainerMonitor é a ÚNICA fonte de alertas de container (ignora alertas de container do Grafana)
PORTAINER_MONITOR_ONLY_SOURCE = os.getenv("PORTAINER_MONITOR_ONLY_SOURCE", "true").lower() == "true"

# Supressão específica para containers
CONTAINER_SUPPRESS_REPEATS = os.getenv("CONTAINER_SUPPRESS_REPEATS", "true").lower() == "true"
CONTAINER_SUPPRESS_TTL_SECONDS = int(os.getenv("CONTAINER_SUPPRESS_TTL_SECONDS", "86400"))  # 24h
CONTAINER_SUPPRESS_PERSIST = os.getenv("CONTAINER_SUPPRESS_PERSIST", "true").lower() == "true"
CONTAINER_SUPPRESS_STATE_FILE = os.getenv("CONTAINER_SUPPRESS_STATE_FILE", "/tmp/proxy-alertmanager-suppression-state.json")
_paused_allowlist_env = os.getenv("CONTAINER_PAUSED_ALLOWLIST", "").strip()
CONTAINER_PAUSED_ALLOWLIST = set([s.strip() for s in _paused_allowlist_env.split(",") if s.strip()])

# Supressão Blue/Green deployment
BLUE_GREEN_SUPPRESSION_ENABLED = os.getenv("BLUE_GREEN_SUPPRESSION_ENABLED", "true").lower() == "true"

# Containers que NUNCA devem ser suprimidos (sempre notificar)
_always_notify_allowlist_env = os.getenv("CONTAINER_ALWAYS_NOTIFY_ALLOWLIST", "").strip()
CONTAINER_ALWAYS_NOTIFY_ALLOWLIST = set([s.strip() for s in _always_notify_allowlist_env.split(",") if s.strip()])

# Containers que devem ser completamente ignorados (sem alertas em nenhum estado)
_ignore_allowlist_env = os.getenv("CONTAINER_IGNORE_ALLOWLIST", "").strip()
CONTAINER_IGNORE_ALLOWLIST = set([s.strip() for s in _ignore_allowlist_env.split(",") if s.strip()])

# Configurações de tipos de alertas com níveis de severidade
ALERT_CONFIGS = {
    "cpu": {"emoji": "🖥️", "name": "CPU", "unit": "%"},
    "memory": {"emoji": "💾", "name": "MEMÓRIA", "unit": "%"},
    "disk": {"emoji": "💿", "name": "DISCO", "unit": "%"},
    "container": {"emoji": "🐳", "name": "CONTAINER", "unit": ""},
    "default": {"emoji": "🚨", "name": "SISTEMA", "unit": ""},
}

SEVERITY_LEVELS = {
    "low": {
        "threshold_min": 0,
        "threshold_max": 80,
        "emoji": "🚧",
        "label": "ATENÇÃO",
        "colors": {
            "cpu": int(os.getenv("CPU_LOW_COLOR", "16776960")),
            "memory": int(os.getenv("MEMORY_LOW_COLOR", "16776960")),
            "disk": int(os.getenv("DISK_LOW_COLOR", "16776960")),
            "default": int(os.getenv("DEFAULT_LOW_COLOR", "16776960")),
        },
        "gifs": {
            "cpu": os.getenv("CPU_LOW_GIF", ""),
            "memory": os.getenv("MEMORY_LOW_GIF", ""),
            "disk": os.getenv("DISK_LOW_GIF", ""),
            "default": os.getenv("DEFAULT_LOW_GIF", ""),
        },
    },
    "medium": {
        "threshold_min": 80,
        "threshold_max": 90,
        "emoji": "⚠️",
        "label": "ALERTA",
        "colors": {
            "cpu": int(os.getenv("CPU_MEDIUM_COLOR", "16753920")),
            "memory": int(os.getenv("MEMORY_MEDIUM_COLOR", "16753920")),
            "disk": int(os.getenv("DISK_MEDIUM_COLOR", "16753920")),
            "default": int(os.getenv("DEFAULT_MEDIUM_COLOR", "16753920")),
        },
        "gifs": {
            "cpu": os.getenv("CPU_MEDIUM_GIF", ""),
            "memory": os.getenv("MEMORY_MEDIUM_GIF", ""),
            "disk": os.getenv("DISK_MEDIUM_GIF", ""),
            "default": os.getenv("DEFAULT_MEDIUM_GIF", ""),
        },
    },
    "high": {
        "threshold_min": 90,
        "threshold_max": 100,
        "emoji": "🔥",
        "label": "CRÍTICO",
        "colors": {
            "cpu": int(os.getenv("CPU_HIGH_COLOR", "16711680")),
            "memory": int(os.getenv("MEMORY_HIGH_COLOR", "16711680")),
            "disk": int(os.getenv("DISK_HIGH_COLOR", "16711680")),
            "default": int(os.getenv("DEFAULT_HIGH_COLOR", "16711680")),
        },
        "gifs": {
            "cpu": os.getenv("CPU_HIGH_GIF", ""),
            "memory": os.getenv("MEMORY_HIGH_GIF", ""),
            "disk": os.getenv("DISK_HIGH_GIF", ""),
            "default": os.getenv("DEFAULT_HIGH_GIF", ""),
        },
    },
    "container_down": {
        "emoji": "🚨",
        "label": "CONTAINER OFFLINE",
        "color": int(os.getenv("CONTAINER_DOWN_COLOR", "16711680")),
        "gif": os.getenv("CONTAINER_DOWN_GIF", ""),
    },
    "container_up": {
        "emoji": "✅",
        "label": "CONTAINER ONLINE",
        "color": int(os.getenv("CONTAINER_UP_COLOR", "65280")),
        "gif": os.getenv("CONTAINER_UP_GIF", ""),
    },
    "resolved": {
        "emoji": "🟢",
        "label": "RESOLVIDO",
        "color": int(os.getenv("RESOLVED_COLOR", "32768")),
        "gif": os.getenv("RESOLVED_GIF", ""),
    },
}
