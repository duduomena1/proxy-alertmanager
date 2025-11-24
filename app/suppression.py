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
)

if TYPE_CHECKING:
    from .portainer import PortainerClient

logger = logging.getLogger(__name__)


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


def build_container_key_by_id(host: Optional[str], container_id: Optional[str]) -> str:
    """
    Variante de chave usando o container_id (estável no Portainer), mantendo o host.
    Prefixa com 'id:' para evitar colisão semântica com nomes iguais a IDs.
    """
    host_key = (host or '').split(':')[0]
    return f"{_normalize_name(host_key)}|id:{_normalize_name(container_id or 'unknown')}"


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


def extract_blue_green_base(container_name: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Detecta se o container segue padrão blue/green e extrai o nome base.
    Suporta: app-blue, app-green, app_blue, app_green (case-insensitive).
    
    Returns:
        (base_name, color) onde color é 'blue' ou 'green', ou (None, None) se não for blue/green.
    
    Exemplos:
        'nginx-blue' -> ('nginx', 'blue')
        'API_GREEN' -> ('api', 'green')
        'app-v1' -> (None, None)
    """
    if not container_name:
        return None, None
    
    # Regex para detectar sufixo -blue/-green ou _blue/_green (case-insensitive)
    pattern = r'^(.+?)[-_](blue|green)$'
    match = re.match(pattern, container_name, re.IGNORECASE)
    
    if match:
        base_name = match.group(1).lower()
        color = match.group(2).lower()
        logger.debug(f"Container '{container_name}' detectado como blue/green: base='{base_name}', color='{color}'")
        return base_name, color
    
    return None, None


def find_active_sibling(container_name: str, endpoint_id: Optional[int], portainer_client: Optional['PortainerClient']) -> Tuple[bool, Optional[str]]:
    """
    Verifica se o sibling blue/green do container está ativo no mesmo endpoint.
    
    Args:
        container_name: Nome do container (ex: 'app-blue')
        endpoint_id: ID do endpoint Portainer
        portainer_client: Cliente Portainer para consultar containers
    
    Returns:
        (sibling_is_active, sibling_name) onde sibling_is_active indica se o par está running.
    
    Exemplos:
        'app-blue' com 'app-green' running -> (True, 'app-green')
        'app-blue' com 'app-green' down -> (False, 'app-green')
        'nginx' sem padrão blue/green -> (False, None)
    """
    if not BLUE_GREEN_SUPPRESSION_ENABLED:
        logger.debug("Blue/green suppression desabilitado (BLUE_GREEN_SUPPRESSION_ENABLED=false)")
        return False, None
    
    if not portainer_client or endpoint_id is None:
        logger.debug(f"Portainer não disponível para verificar sibling de '{container_name}'")
        return False, None
    
    base_name, color = extract_blue_green_base(container_name)
    if not base_name or not color:
        # Não é um container blue/green
        return False, None
    
    # Determinar o nome do sibling (trocar blue <-> green)
    sibling_color = 'green' if color == 'blue' else 'blue'
    
    # Reconstruir possíveis nomes do sibling (preservar separador original)
    # Detectar separador usado no nome original
    separator = '-' if '-' in container_name[-6:] else '_'  # Últimos 6 chars devem conter o separador
    sibling_name = f"{base_name}{separator}{sibling_color}"
    
    logger.debug(f"Procurando sibling '{sibling_name}' para container '{container_name}' no endpoint {endpoint_id}")
    
    try:
        # Listar todos os containers do endpoint
        containers = portainer_client.list_containers(endpoint_id, all=True)
        
        # Procurar o sibling e verificar seu estado
        for container in containers:
            # Docker API retorna Names como lista ['/nome'] ou campo Name
            container_names = container.get('Names', [])
            if isinstance(container_names, list):
                container_names = [n.lstrip('/') for n in container_names]
            else:
                container_names = [container.get('Name', '').lstrip('/')]
            
            # Comparar case-insensitive
            for name in container_names:
                if name.lower() == sibling_name.lower():
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
    """
    State machine simples por container para suprimir alertas repetidos.
    Regras:
    - Envia 1º alerta quando entra em estado problemático (down/restarting/exited...)
    - Suprime os seguintes enquanto não voltar a 'running'
    - Ao ver 'running', reseta supressão
    - 'paused' é ignorado se o container estiver na allowlist
    """

    FAILURE_STATES = {'down', 'restarting', 'exited', 'dead', 'unknown', 'stopped', 'created'}

    def __init__(self, ttl_seconds: int = CONTAINER_SUPPRESS_TTL_SECONDS, enabled: bool = CONTAINER_SUPPRESS_REPEATS, 
                 persist: bool = CONTAINER_SUPPRESS_PERSIST, state_file: str = CONTAINER_SUPPRESS_STATE_FILE):
        self.enabled = enabled
        self.ttl = ttl_seconds
        self.persist = persist
        self.state_file = state_file
        self._store: Dict[str, Dict] = {}
        
        # Carrega estado persistido (se habilitado)
        if self.persist:
            self._load_state()

    def _load_state(self):
        """Carrega estado de supressão de arquivo JSON."""
        if not os.path.exists(self.state_file):
            return
        
        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)
                # Carrega apenas entradas ainda válidas (dentro do TTL)
                now = time.time()
                for key, entry in data.items():
                    if isinstance(entry, dict) and 'ts' in entry:
                        if (now - entry.get('ts', now)) <= self.ttl:
                            self._store[key] = entry
                
                logger.info(f"Estado de supressão carregado: {len(self._store)} containers suprimidos")
        except Exception as e:
            logger.warning(f"Falha ao carregar estado de supressão: {e}")

    def _save_state(self):
        """Salva estado de supressão em arquivo JSON."""
        if not self.persist:
            return
        
        try:
            # Garante que o diretório existe
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
        
        # Salva estado após limpeza (se habilitado)
        if to_delete and self.persist:
            self._save_state()

    def should_send(self, key: str, current_state: str, container_name: Optional[str] = None, 
                    portainer_client: Optional['PortainerClient'] = None, endpoint_id: Optional[int] = None) -> Tuple[bool, str]:
        """
        Retorna (deve_enviar, motivo). Quando suprime, motivo explica.
        
        Args:
            key: Chave única do container
            current_state: Estado atual ('running', 'down', etc.)
            container_name: Nome do container para verificações de allowlist e blue/green
            portainer_client: Cliente Portainer para verificar sibling blue/green
            endpoint_id: ID do endpoint Portainer onde o container está rodando
        """
        self._cleanup()
        if not self.enabled:
            return True, 'feature_disabled'

        name_norm = _normalize_name(container_name or '')
        # Containers completamente ignorados (sem alertas)
        if name_norm in { _normalize_name(n) for n in CONTAINER_IGNORE_ALLOWLIST }:
            return False, 'completely_ignored'
        # Containers no allowlist de "sempre notificar" nunca são suprimidos
        if name_norm in { _normalize_name(n) for n in CONTAINER_ALWAYS_NOTIFY_ALLOWLIST }:
            return True, 'always_notify_allowlisted'
        # Ignorar 'paused' quando na allowlist
        if current_state == 'paused' and name_norm in { _normalize_name(n) for n in CONTAINER_PAUSED_ALLOWLIST }:
            # Mantém registro mas não ativa supressão
            self._store[key] = {'suppressed': False, 'last': 'paused', 'ts': time.time()}
            self._save_state()
            return False, 'paused_allowlisted'

        entry = self._store.get(key, {'suppressed': False, 'last': 'unknown', 'ts': 0})

        # Reset ao ver running
        if current_state == 'running':
            self._store[key] = {'suppressed': False, 'last': 'running', 'ts': time.time()}
            self._save_state()
            return False, 'reset_on_running'

        # Estados problemáticos
        if current_state in self.FAILURE_STATES:
            # VERIFICAÇÃO BLUE/GREEN: Se o sibling estiver ativo, suprimir alerta
            if container_name and portainer_client and endpoint_id is not None:
                sibling_active, sibling_name = find_active_sibling(container_name, endpoint_id, portainer_client)
                if sibling_active and sibling_name:
                    logger.info(f"Suprimindo alerta de '{container_name}': sibling '{sibling_name}' está ativo (blue/green deployment)")
                    # Atualizar estado mas não ativar supressão (para permitir alerta se ambos caírem)
                    entry.update({'last': current_state, 'ts': time.time(), 'suppressed': False})
                    self._store[key] = entry
                    self._save_state()
                    return False, f'blue_green_sibling_active:{sibling_name}'
            
            if entry.get('suppressed'):
                # já alertou antes e não voltou a running
                entry.update({'last': current_state, 'ts': time.time()})
                self._store[key] = entry
                self._save_state()
                return False, 'already_suppressed_until_running'
            # primeira falha desde último running -> envia e ativa supressão
            self._store[key] = {'suppressed': True, 'last': current_state, 'ts': time.time()}
            self._save_state()
            return True, 'first_failure_since_running'

        # Outros estados desconhecidos: não envia por padrão
        entry.update({'last': current_state, 'ts': time.time()})
        self._store[key] = entry
        self._save_state()
        return False, 'non_failure_state'
