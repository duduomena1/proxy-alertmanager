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
# Período de graça (segundos) para aguardar o sibling blue/green subir antes de alertar
BLUE_GREEN_GRACE_SECONDS = int(os.getenv("BLUE_GREEN_GRACE_SECONDS", "120"))

# Containers que NUNCA devem ser suprimidos (sempre notificar)
_always_notify_allowlist_env = os.getenv("CONTAINER_ALWAYS_NOTIFY_ALLOWLIST", "").strip()
CONTAINER_ALWAYS_NOTIFY_ALLOWLIST = set([s.strip() for s in _always_notify_allowlist_env.split(",") if s.strip()])

# Containers que devem ser completamente ignorados (sem alertas em nenhum estado)
_ignore_allowlist_env = os.getenv("CONTAINER_IGNORE_ALLOWLIST", "").strip()
CONTAINER_IGNORE_ALLOWLIST = set([s.strip() for s in _ignore_allowlist_env.split(",") if s.strip()])

# Configurações de tipos de alertas — inclui GIF único por tipo (independente de severidade)
ALERT_CONFIGS = {
    "cpu":       {"emoji": "🖥️",  "name": "CPU",      "unit": "%", "gif": os.getenv("CPU_GIF", "")},
    "memory":    {"emoji": "💾",  "name": "MEMÓRIA",  "unit": "%", "gif": os.getenv("MEMORY_GIF", "")},
    "disk":      {"emoji": "💿",  "name": "DISCO",    "unit": "%", "gif": os.getenv("DISK_GIF", "")},
    "container": {"emoji": "🐳",  "name": "CONTAINER", "unit": "", "gif": ""},
    "default":   {"emoji": "🚨",  "name": "SISTEMA",  "unit": "", "gif": os.getenv("DEFAULT_GIF", "")},
}

SEVERITY_LEVELS = {
    "low": {
        "threshold_min": 0,
        "threshold_max": 80,
        "emoji": "🚧",
        "label": "ATENÇÃO",
        "color": int(os.getenv("LOW_COLOR", "16776960")),   # Amarelo
    },
    "medium": {
        "threshold_min": 80,
        "threshold_max": 90,
        "emoji": "⚠️",
        "label": "ALERTA",
        "color": int(os.getenv("MEDIUM_COLOR", "16753920")),  # Laranja
    },
    "high": {
        "threshold_min": 90,
        "threshold_max": 100,
        "emoji": "🔥",
        "label": "CRÍTICO",
        "color": int(os.getenv("HIGH_COLOR", "16711680")),   # Vermelho
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
    "uptimekuma_up": {
        "emoji": "✅",
        "label": "UP",
        "color": int(os.getenv("UPTIME_KUMA_UP_COLOR", "65280")),
        "gif": os.getenv("UPTIME_KUMA_GIF", ""),
    },
    "uptimekuma_down": {
        "emoji": "🔴",
        "label": "DOWN",
        "color": int(os.getenv("UPTIME_KUMA_DOWN_COLOR", "16711680")),
        "gif": os.getenv("UPTIME_KUMA_GIF", ""),
    },
    "uptimekuma_default": {
        "emoji": "📡",
        "label": "UPTIME KUMA",
        "color": int(os.getenv("UPTIME_KUMA_DEFAULT_COLOR", "2201331")),
        "gif": os.getenv("UPTIME_KUMA_GIF", ""),
    },
    "hetrix_up": {
        "emoji": "✅",
        "label": "ONLINE",
        "color": int(os.getenv("HETRIX_UP_COLOR", "65280")),
        "gif": os.getenv("HETRIX_GIF", ""),
    },
    "hetrix_down": {
        "emoji": "🔴",
        "label": "OFFLINE",
        "color": int(os.getenv("HETRIX_DOWN_COLOR", "16711680")),
        "gif": os.getenv("HETRIX_GIF", ""),
    },
    "hetrix_default": {
        "emoji": "📡",
        "label": "HETRIX",
        "color": int(os.getenv("HETRIX_DEFAULT_COLOR", "2201331")),
        "gif": os.getenv("HETRIX_GIF", ""),
    },

}