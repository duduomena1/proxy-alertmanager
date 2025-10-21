import time
from typing import Dict, Optional


class TTLCache:
    def __init__(self, ttl_seconds: int, max_size: int = 5000):
        self.ttl = ttl_seconds
        self.max_size = max_size
        self._store: Dict[str, float] = {}

    def _evict_if_needed(self):
        # Remove expirados e controla tamanho
        now = time.time()
        expired_keys = [k for k, ts in self._store.items() if (now - ts) > self.ttl]
        for k in expired_keys:
            self._store.pop(k, None)
        # Se ainda acima do limite, evict por ordem de idade (aprox.)
        if len(self._store) > self.max_size:
            # Ordena por timestamp (mais antigo primeiro)
            for k in sorted(self._store, key=self._store.get)[: (len(self._store) - self.max_size)]:
                self._store.pop(k, None)

    def touch(self, key: str):
        self._store[key] = time.time()
        self._evict_if_needed()

    def is_within_ttl(self, key: str) -> bool:
        ts = self._store.get(key)
        if ts is None:
            return False
        return (time.time() - ts) <= self.ttl


def build_alert_fingerprint(alert_type: str, labels: dict, enriched_info: dict, alert_status: str | None = None) -> str:
    host = enriched_info.get('real_ip') or enriched_info.get('clean_host') or labels.get('instance')
    host = (host or '').split(':')[0]
    # campos relevantes por tipo
    if alert_type == 'disk':
        device = labels.get('device') or labels.get('fstype') or labels.get('mountpoint', '/')
        parts = [alert_type, host, str(device)]
    elif alert_type == 'container':
        container = labels.get('container') or labels.get('container_name') or labels.get('pod') or labels.get('name')
        parts = [alert_type, host, str(container)]
    else:
        # cpu/memory/default por host apenas
        parts = [alert_type, host]
    # status também entra para não suprimir RESOLVED de um FIRING anterior
    if alert_status:
        parts.append(alert_status.lower())
    return '|'.join([p for p in parts if p])
