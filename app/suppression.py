import time
import re
import logging
import json
import os
from typing import Dict, Optional, Tuple, TYPE_CHECKING

from .constants import (
    CONTAINER_SUPPRESS_REPEATS,
    CONTAINER_SUPPRESS_TTL_SECONDS,
    CONTAINER_SUPPRESS_PERSIST,
    CONTAINER_SUPPRESS_STATE_FILE,
    CONTAINER_PAUSED_ALLOWLIST,
    CONTAINER_ALWAYS_NOTIFY_ALLOWLIST,
    CONTAINER_IGNORE_ALLOWLIST,
    BLUE_GREEN_SUPPRESSION_ENABLED,
    BLUE_GREEN_GRACE_SECONDS,
)

if TYPE_CHECKING:
    from .portainer import PortainerClient

logger = logging.getLogger(__name__)


def _normalize_name(value: Optional[str]) -> str:
    if not value:
        return ""
    return str(value).strip().lower()


def build_container_key(host: Optional[str], labels: Dict) -> str:
    host_key = (host or labels.get('host_ip') or labels.get('real_host') or labels.get('instance') or 'unknown')
    host_key = str(host_key).split(':')[0]
    cname = labels.get('container') or labels.get('container_name') or labels.get('pod') or labels.get('name') or 'unknown'
    return f"{_normalize_name(host_key)}|{_normalize_name(cname)}"


def build_container_key_by_id(host: Optional[str], container_id: Optional[str]) -> str:
    host_key = (host or '').split(':')[0]
    return f"{_normalize_name(host_key)}|id:{_normalize_name(container_id or 'unknown')}"


def compute_state(portainer_result: Optional[Dict], metric_value: Optional[float], alert_status: str) -> str:
    if portainer_result and portainer_result.get('enabled') and portainer_result.get('verified'):
        running = bool(portainer_result.get('running'))
        status_raw = (portainer_result.get('status') or ('running' if running else 'unknown')).lower()
        if status_raw in ['running']:
            return 'running'
        if status_raw in ['restarting', 'paused', 'exited', 'dead', 'created']:
            return status_raw
        return 'down' if not running else 'running'

    if alert_status and alert_status.lower() == 'resolved' and (metric_value == 1):
        return 'running'
    if alert_status and alert_status.lower() == 'firing' and (metric_value == 0):
        return 'down'

    return 'unknown'


def extract_blue_green_base(container_name: str) -> Tuple[Optional[str], Optional[str]]:
    if not container_name:
        return None, None
    
    import re
    cleaned_name = re.sub(r'^[0-9a-f]{12,}_', '', container_name, flags=re.IGNORECASE)
    
    pattern = r'^(.+?)[-_](blue|green)$'
    match = re.match(pattern, cleaned_name, re.IGNORECASE)
    
    if match:
        base_name = match.group(1).lower()
        color = match.group(2).lower()
        if cleaned_name != container_name:
            logger.debug(f"Container '{container_name}' tem ID prefixado, nome limpo: '{cleaned_name}'")
        logger.debug(f"Container '{cleaned_name}' detectado como blue/green: base='{base_name}', color='{color}'")
        return base_name, color
    
    return None, None


def find_active_sibling(container_name: str, endpoint_id: Optional[int], portainer_client: Optional['PortainerClient']) -> Tuple[bool, Optional[str]]:
    if not BLUE_GREEN_SUPPRESSION_ENABLED:
        logger.debug("Blue/green suppression desabilitado (BLUE_GREEN_SUPPRESSION_ENABLED=false)")
        return False, None
    
    if not portainer_client or endpoint_id is None:
        logger.debug(f"Portainer não disponível para verificar sibling de '{container_name}'")
        return False, None
    
    base_name, color = extract_blue_green_base(container_name)
    if not base_name or not color:
        return False, None
    
    sibling_color = 'green' if color == 'blue' else 'blue'
    
    import re
    cleaned_name = re.sub(r'^[0-9a-f]{12,}_', '', container_name, flags=re.IGNORECASE)
    separator = cleaned_name[len(base_name)]
    sibling_name = f"{base_name}{separator}{sibling_color}"
    
    logger.debug(f"Procurando sibling '{sibling_name}' para container '{container_name}' no endpoint {endpoint_id}")
    
    try:
        containers = portainer_client.list_containers(endpoint_id, all=True)
        
        for container in containers:
            container_names = container.get('Names', [])
            if isinstance(container_names, list):
                container_names = [n.lstrip('/') for n in container_names]
            else:
                container_names = [container.get('Name', '').lstrip('/')]
            
            for name in container_names:
                clean_name = re.sub(r'^[0-9a-f]{12,}_', '', name, flags=re.IGNORECASE)
                if clean_name.lower() == sibling_name.lower():
                    state = container.get('State', '').lower()
                    is_running = state == 'running'
                    logger.debug(f"Sibling '{name}' encontrado com estado '{state}' (running={is_running})")
                    return is_running, name
        
        logger.debug(f"Sibling '{sibling_name}' não encontrado no endpoint {endpoint_id}")
        return False, sibling_name
        
    except Exception as e:
        logger.warning(f"Erro ao verificar sibling blue/green para '{container_name}': {e}")
        return False, None


class ContainerSuppressor:

    FAILURE_STATES = {'down', 'restarting', 'exited', 'dead', 'unknown', 'stopped', 'created'}

    def __init__(self, ttl_seconds: int = CONTAINER_SUPPRESS_TTL_SECONDS, enabled: bool = CONTAINER_SUPPRESS_REPEATS, 
                 persist: bool = CONTAINER_SUPPRESS_PERSIST, state_file: str = CONTAINER_SUPPRESS_STATE_FILE):
        self.enabled = enabled
        self.ttl = ttl_seconds
        self.persist = persist
        self.state_file = state_file
        self._store: Dict[str, Dict] = {}
        
        if self.persist:
            self._load_state()

    def _load_state(self):
        if not os.path.exists(self.state_file):
            return
        
        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)
                now = time.time()
                for key, entry in data.items():
                    if isinstance(entry, dict) and 'ts' in entry:
                        if (now - entry.get('ts', now)) <= self.ttl:
                            self._store[key] = entry
                
                logger.info(f"Estado de supressão carregado: {len(self._store)} containers suprimidos")
        except Exception as e:
            logger.warning(f"Falha ao carregar estado de supressão: {e}")

    def _save_state(self):
        if not self.persist:
            return
        
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            
            with open(self.state_file, 'w') as f:
                json.dump(self._store, f, indent=2)
        except Exception as e:
            logger.warning(f"Falha ao salvar estado de supressão: {e}")

    def _cleanup(self):
        now = time.time()
        to_delete = []
        for k, v in self._store.items():
            if (now - v.get('ts', now)) > self.ttl:
                to_delete.append(k)
        for k in to_delete:
            self._store.pop(k, None)
        
        if to_delete and self.persist:
            self._save_state()

    def should_send(self, key: str, current_state: str, container_name: Optional[str] = None, 
                    portainer_client: Optional['PortainerClient'] = None, endpoint_id: Optional[int] = None) -> Tuple[bool, str]:
        self._cleanup()
        if not self.enabled:
            return True, 'feature_disabled'

        name_norm = _normalize_name(container_name or '')
        if name_norm in { _normalize_name(n) for n in CONTAINER_IGNORE_ALLOWLIST }:
            return False, 'completely_ignored'
        if name_norm in { _normalize_name(n) for n in CONTAINER_ALWAYS_NOTIFY_ALLOWLIST }:
            return True, 'always_notify_allowlisted'
        if current_state == 'paused' and name_norm in { _normalize_name(n) for n in CONTAINER_PAUSED_ALLOWLIST }:
            self._store[key] = {'suppressed': False, 'last': 'paused', 'ts': time.time()}
            self._save_state()
            return False, 'paused_allowlisted'

        entry = self._store.get(key, {'suppressed': False, 'last': 'unknown', 'ts': 0})

        if current_state == 'running':
            self._store[key] = {'suppressed': False, 'last': 'running', 'ts': time.time(), 'bg_grace': None}
            self._save_state()
            return False, 'reset_on_running'

        if current_state in self.FAILURE_STATES:
            if container_name and portainer_client and endpoint_id is not None:
                sibling_active, sibling_name = find_active_sibling(container_name, endpoint_id, portainer_client)

                if sibling_active:
                    if DEBUG_MODE:
                        print(f"[DEBUG] 🔵🟢 Suprimindo alerta de '{container_name}': sibling '{sibling_name}' está ATIVO (deploy blue/green confirmado)")
                    logger.info(f"Suprimindo alerta de '{container_name}': sibling '{sibling_name}' está ativo (blue/green deployment)")
                    entry.update({'last': current_state, 'ts': time.time(), 'suppressed': False, 'bg_grace': None})
                    self._store[key] = entry
                    self._save_state()
                    return False, f'blue_green_sibling_active:{sibling_name}'

                base_name, color = extract_blue_green_base(container_name)
                if base_name and color and BLUE_GREEN_SUPPRESSION_ENABLED:
                    now = time.time()
                    grace_start = entry.get('bg_grace')
                    if grace_start is None:
                        entry.update({'last': current_state, 'ts': now, 'suppressed': False, 'bg_grace': now})
                        self._store[key] = entry
                        self._save_state()
                        if DEBUG_MODE:
                            print(f"[DEBUG] 🔵🟢 Iniciando período de graça de {BLUE_GREEN_GRACE_SECONDS}s para '{container_name}' (aguardando sibling '{sibling_name}' subir)")
                        logger.info(f"Blue/green: iniciando período de graça de {BLUE_GREEN_GRACE_SECONDS}s para '{container_name}' (sibling={sibling_name})")
                        return False, f'blue_green_grace_started:{sibling_name or ""}'
                    elapsed = now - grace_start
                    if elapsed < BLUE_GREEN_GRACE_SECONDS:
                        if DEBUG_MODE:
                            remaining = int(BLUE_GREEN_GRACE_SECONDS - elapsed)
                            print(f"[DEBUG] 🔵🟢 Aguardando sibling '{sibling_name}' subir: {int(elapsed)}s/{BLUE_GREEN_GRACE_SECONDS}s (faltam {remaining}s)")
                        entry.update({'last': current_state, 'ts': now})
                        self._store[key] = entry
                        self._save_state()
                        return False, f'blue_green_grace_waiting:{sibling_name or ""}:{int(elapsed)}s'
                    if DEBUG_MODE:
                        print(f"[DEBUG] 🔵🟢 ⚠️ Período de graça EXPIROU ({int(elapsed)}s) para '{container_name}' → sibling '{sibling_name}' NÃO subiu, tratando como FALHA REAL")
                    logger.warning(f"Blue/green: período de graça expirou ({int(elapsed)}s) para '{container_name}' sem sibling subir → falha real confirmada")
                    entry['bg_grace'] = None

            if entry.get('suppressed'):
                entry.update({'last': current_state, 'ts': time.time()})
                self._store[key] = entry
                self._save_state()
                return False, 'already_suppressed_until_running'
            self._store[key] = {'suppressed': True, 'last': current_state, 'ts': time.time()}
            self._save_state()
            return True, 'first_failure_since_running'

        entry.update({'last': current_state, 'ts': time.time()})
        self._store[key] = entry
        self._save_state()
        return False, 'non_failure_state'
