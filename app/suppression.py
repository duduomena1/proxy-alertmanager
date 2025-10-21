import time
from typing import Dict, Optional, Tuple

from .constants import (
    CONTAINER_SUPPRESS_REPEATS,
    CONTAINER_SUPPRESS_TTL_SECONDS,
    CONTAINER_PAUSED_ALLOWLIST,
)


def _normalize_name(value: Optional[str]) -> str:
    if not value:
        return ""
    return str(value).strip().lower()


def build_container_key(host: Optional[str], labels: Dict) -> str:
    """
    Gera uma chave única para o container considerando host e nome.
    Usa ordem de preferência semelhante ao dedupe: container, container_name, pod, name.
    """
    host_key = (host or labels.get('host_ip') or labels.get('real_host') or labels.get('instance') or 'unknown')
    host_key = str(host_key).split(':')[0]
    cname = labels.get('container') or labels.get('container_name') or labels.get('pod') or labels.get('name') or 'unknown'
    return f"{_normalize_name(host_key)}|{_normalize_name(cname)}"


def compute_state(portainer_result: Optional[Dict], metric_value: Optional[float], alert_status: str) -> str:
    """
    Determina estado atual do container usando (na ordem): Portainer -> métricas Grafana.
    Estados retornados: 'running', 'restarting', 'paused', 'exited', 'dead', 'down', 'unknown'.
    """
    # 1) Tenta usar Portainer se existir um resultado verificado
    if portainer_result and portainer_result.get('enabled') and portainer_result.get('verified'):
        running = bool(portainer_result.get('running'))
        status_raw = (portainer_result.get('status') or ('running' if running else 'unknown')).lower()
        if status_raw in ['running']:
            return 'running'
        if status_raw in ['restarting', 'paused', 'exited', 'dead', 'created']:
            return status_raw
        # Se não reconhecido e não está running, trata como 'down'
        return 'down' if not running else 'running'

    # 2) Fallback pelas métricas do Grafana
    # Convenção existente no projeto:
    #  - value=0 + status=firing   -> DOWN
    #  - value=1 + status=resolved -> UP (running)
    if alert_status and alert_status.lower() == 'resolved' and (metric_value == 1):
        return 'running'
    if alert_status and alert_status.lower() == 'firing' and (metric_value == 0):
        return 'down'

    return 'unknown'


class ContainerSuppressor:
    """
    State machine simples por container para suprimir alertas repetidos.
    Regras:
    - Envia 1º alerta quando entra em estado problemático (down/restarting/exited...)
    - Suprime os seguintes enquanto não voltar a 'running'
    - Ao ver 'running', reseta supressão
    - 'paused' é ignorado se o container estiver na allowlist
    """

    FAILURE_STATES = {'down', 'restarting', 'exited', 'dead', 'unknown', 'stopped', 'created'}

    def __init__(self, ttl_seconds: int = CONTAINER_SUPPRESS_TTL_SECONDS, enabled: bool = CONTAINER_SUPPRESS_REPEATS):
        self.enabled = enabled
        self.ttl = ttl_seconds
        self._store: Dict[str, Dict] = {}

    def _cleanup(self):
        now = time.time()
        to_delete = []
        for k, v in self._store.items():
            if (now - v.get('ts', now)) > self.ttl:
                to_delete.append(k)
        for k in to_delete:
            self._store.pop(k, None)

    def should_send(self, key: str, current_state: str, container_name: Optional[str] = None) -> Tuple[bool, str]:
        """
        Retorna (deve_enviar, motivo). Quando suprime, motivo explica.
        """
        self._cleanup()
        if not self.enabled:
            return True, 'feature_disabled'

        name_norm = _normalize_name(container_name or '')
        # Ignorar 'paused' quando na allowlist
        if current_state == 'paused' and name_norm in { _normalize_name(n) for n in CONTAINER_PAUSED_ALLOWLIST }:
            # Mantém registro mas não ativa supressão
            self._store[key] = {'suppressed': False, 'last': 'paused', 'ts': time.time()}
            return False, 'paused_allowlisted'

        entry = self._store.get(key, {'suppressed': False, 'last': 'unknown', 'ts': 0})

        # Reset ao ver running
        if current_state == 'running':
            self._store[key] = {'suppressed': False, 'last': 'running', 'ts': time.time()}
            return False, 'reset_on_running'

        # Estados problemáticos
        if current_state in self.FAILURE_STATES:
            if entry.get('suppressed'):
                # já alertou antes e não voltou a running
                entry.update({'last': current_state, 'ts': time.time()})
                self._store[key] = entry
                return False, 'already_suppressed_until_running'
            # primeira falha desde último running -> envia e ativa supressão
            self._store[key] = {'suppressed': True, 'last': current_state, 'ts': time.time()}
            return True, 'first_failure_since_running'

        # Outros estados desconhecidos: não envia por padrão
        entry.update({'last': current_state, 'ts': time.time()})
        self._store[key] = entry
        return False, 'non_failure_state'
