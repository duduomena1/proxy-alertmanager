import threading
import time
from typing import Dict, List, Optional, Tuple

from .constants import (
    DEBUG_MODE,
    ALERT_DEDUP_ENABLED,
    ALERT_COOLDOWN_SECONDS,
    CONTAINER_ALWAYS_NOTIFY_ALLOWLIST,
    PORTAINER_ACTIVE_MONITOR,
    PORTAINER_MONITOR_INTERVAL_SECONDS,
    PORTAINER_MONITOR_ENDPOINTS,
    PORTAINER_MONITOR_DOWN_CONFIRMATIONS,
    PORTAINER_MONITOR_SCOPE,
)
from .portainer import portainer_client
from .dedupe import TTLCache, build_alert_fingerprint
from .formatters import format_container_alert
from .utils import format_timestamp
from .services import send_discord_payload
from .suppression import ContainerSuppressor, build_container_key, build_container_key_by_id


class PortainerMonitor(threading.Thread):
    def __init__(self, dedupe_cache: TTLCache):
        super().__init__(daemon=True)
        self.dedupe_cache = dedupe_cache
        self._stop = threading.Event()
        self._prev_state: Dict[Tuple[int, str], bool] = {}
        # (endpoint_id, container_id) -> running
        self.interval = PORTAINER_MONITOR_INTERVAL_SECONDS
        self.filter_endpoints: Optional[List[str]] = (
            [s.strip().lower() for s in PORTAINER_MONITOR_ENDPOINTS.split(',') if s.strip()]
            if PORTAINER_MONITOR_ENDPOINTS
            else None
        )
        # Contadores para histerese (reduz falsos positivos)
        self._running_counts: Dict[Tuple[int, str], int] = {}
        self._down_counts: Dict[Tuple[int, str], int] = {}
        self.down_confirmations = max(1, PORTAINER_MONITOR_DOWN_CONFIRMATIONS)
        # Supressor de repetição por container
        self.suppressor = ContainerSuppressor()

    def stop(self):
        self._stop.set()

    def _should_monitor_endpoint(self, endpoint_id: int, endpoint_name: str) -> bool:
        key_id = str(endpoint_id).lower()
        key_name = str(endpoint_name or '').strip().lower()
        # Se filtro explícito está configurado, usa-o
        if self.filter_endpoints:
            return key_id in self.filter_endpoints or key_name in self.filter_endpoints
        # Caso contrário, se escopo = 'map', restringe aos endpoints presentes no mapa
        if PORTAINER_MONITOR_SCOPE == 'map':
            map_values = set(portainer_client.endpoint_map.values())
            in_map_by_id = endpoint_id in map_values
            if in_map_by_id:
                return True
            # fallback: se o nome do endpoint existe como chave no mapa, tratar como permitido
            if key_name in portainer_client.endpoint_map:
                mapped_val = portainer_client.endpoint_map.get(key_name)
                if DEBUG_MODE and mapped_val != endpoint_id:
                    print(f"[DEBUG] PortainerMonitor: nome '{endpoint_name}' está no mapa mas com ID diferente (map={mapped_val}, real={endpoint_id}). Considere atualizar config/portainer_endpoints.json.")
                return True
            if DEBUG_MODE:
                print(f"[DEBUG] PortainerMonitor: ignorando endpoint fora do mapa (eid={endpoint_id}, name={endpoint_name})")
            return False
        # Escopo 'all': monitora tudo
        return True

    def run(self):
        if DEBUG_MODE:
            print(f"[DEBUG] PortainerMonitor iniciado (intervalo={self.interval}s)")
        if not portainer_client.enabled:
            if DEBUG_MODE:
                print("[DEBUG] PortainerMonitor abortado: client desabilitado")
            return

        while not self._stop.is_set():
            try:
                self._loop_once()
            except Exception as exc:
                if DEBUG_MODE:
                    print(f"[DEBUG] PortainerMonitor erro no loop: {exc}")
            self._stop.wait(self.interval)

    def _loop_once(self):
        endpoints = portainer_client.list_endpoints()
        for eid, meta in endpoints.items():
            name = meta.get('Name') or str(eid)
            if not self._should_monitor_endpoint(eid, name):
                continue

            # Lista todos os containers (inclui parados) para transições DOWN
            try:
                all_containers = portainer_client.list_containers(eid, all=True)
            except Exception as exc:
                if DEBUG_MODE:
                    print(f"[DEBUG] PortainerMonitor falha ao listar containers endpoint {eid}: {exc}")
                continue

            # Monta snapshot atual
            current: Dict[Tuple[int, str], bool] = {}
            for entry in all_containers or []:
                cid = entry.get('Id')
                if not cid:
                    continue
                state = entry.get('State') or ''
                status = entry.get('Status') or ''
                s_state = str(state).lower()
                s_status = str(status).lower()
                combined = f"{s_state} {s_status}".strip()
                # Considera 'paused' como não-running, e estados óbvios de down
                is_paused = 'paused' in combined
                is_exited = 'exited' in combined or 'dead' in combined or 'created' in combined or 'stopped' in combined or 'removing' in combined
                # running se: state indica running OU status começa com 'up', mas não estiver paused
                running = ((s_state == 'running') or s_status.startswith('up')) and not (is_paused or is_exited)
                current[(eid, cid)] = running

                # Reset de supressão somente quando running; não ativar supressão no tick
                try:
                    if running:
                        names = entry.get('Names') or []
                        container_name = names[0].lstrip('/') if names else entry.get('Id', 'desconhecido')[:12]
                        mapped_ip = portainer_client.get_host_for_endpoint(eid)
                        cid = entry.get('Id')
                        key = build_container_key_by_id(mapped_ip, cid)
                        _send, reason = self.suppressor.should_send(key, 'running', container_name=container_name)
                        if DEBUG_MODE and reason == 'reset_on_running':
                            print(f"[DEBUG] PortainerMonitor: reset suppression on running for key={key}")
                except Exception as exc:
                    if DEBUG_MODE:
                        print(f"[DEBUG] PortainerMonitor: erro ao resetar suppressor: {exc}")

                # Atualiza contadores de histerese
                key = (eid, cid)
                if running:
                    self._running_counts[key] = self._running_counts.get(key, 0) + 1
                    self._down_counts[key] = 0
                else:
                    # se não está rodando, incrementa contador de 'down' consecutivo
                    self._running_counts.setdefault(key, 0)
                    self._down_counts[key] = self._down_counts.get(key, 0) + 1

                # Detecta transição RUNNING -> NÃO RUNNING (queda)
                prev = self._prev_state.get((eid, cid))
                if prev is True and running is False:
                    # Requer múltiplas confirmações para reduzir falsos positivos
                    if self._down_counts.get(key, 0) >= self.down_confirmations:
                        self._emit_down_alert(eid, entry)
                    else:
                        if DEBUG_MODE:
                            rn = entry.get('Names', [''])[0].lstrip('/') if entry.get('Names') else (cid[:12])
                            print(f"[DEBUG] PortainerMonitor: queda não confirmada (eid={eid}, name={rn}, down_count={self._down_counts.get(key,0)}, ran_count={self._running_counts.get(key,0)})")
                # Novo: caso ainda não tenhamos visto este container running antes (prev != True), mas ele está
                # em estado não-running por confirmações suficientes (ex.: paused), emitir também.
                elif prev is not True and running is False:
                    if self._down_counts.get(key, 0) >= self.down_confirmations:
                        self._emit_down_alert(eid, entry)
                    else:
                        if DEBUG_MODE:
                            rn = entry.get('Names', [''])[0].lstrip('/') if entry.get('Names') else (cid[:12])
                            print(f"[DEBUG] PortainerMonitor: estado não-running observado (eid={eid}, name={rn}), aguardando confirmações (down_count={self._down_counts.get(key,0)})")

            # Atualiza transições para containers que sumiram da lista (ex.: removidos)
            for (peid, pcid), was_running in list(self._prev_state.items()):
                if peid != eid:
                    continue
                if (peid, pcid) not in current and was_running is True:
                    # Container não aparece: confirmar com histerese antes de alertar
                    key = (peid, pcid)
                    self._down_counts[key] = self._down_counts.get(key, 0) + 1
                    if self._down_counts[key] >= self.down_confirmations:
                        phantom = {'Id': pcid, 'Names': [], 'State': 'exited'}
                        self._emit_down_alert(eid, phantom)
                    else:
                        if DEBUG_MODE:
                            print(f"[DEBUG] PortainerMonitor: desaparecimento não confirmado (eid={eid}, cid={pcid[:12]}, down_count={self._down_counts.get(key,0)}, ran_count={self._running_counts.get(key,0)})")

            # Persiste snapshot
            for key, val in current.items():
                self._prev_state[key] = val

            # Limpa contadores de chaves muito antigas (não vistas no snapshot atual)
            stale_keys = [k for k in list(self._running_counts.keys()) if k[0] == eid and k not in current]
            for sk in stale_keys:
                # mantemos down_counts para confirmar desaparecimento por alguns ciclos; não removemos imediatamente
                pass

    def _emit_down_alert(self, endpoint_id: int, container_entry: Dict):
        # Extrai nome
        names = container_entry.get('Names') or []
        container_name = names[0].lstrip('/') if names else container_entry.get('Id', 'desconhecido')[:12]

        if DEBUG_MODE:
            print(f"[DEBUG] PortainerMonitor: queda detectada - endpoint={endpoint_id} container={container_name}")

        # Monta pseudo alerta para reutilizar o formatter existente
        alert_data = {
            'status': 'firing',
            'labels': {
                'alertname': f'ContainerDown - {container_name}',
                'container': container_name,
                'job': 'portainer-monitor',
            },
            'annotations': {
                'description': f'Container {container_name} ficou OFFLINE (Portainer)',
                'summary': f'{container_name} DOWN',
            },
            'startsAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'values': {'A': 0},
            'valueString': 'value=0',
        }
        # Tenta usar IP do endpoint a partir do mapa
        mapped_ip = portainer_client.get_host_for_endpoint(endpoint_id)
        enriched_info = {
            'real_ip': mapped_ip,
            'prometheus_source': 'portainer',
            'original_instance': None,
            'clean_host': mapped_ip or 'unknown',
            'timestamp_processed': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        }
        severity_config = {
            'emoji': '🚨',
            'label': 'CONTAINER OFFLINE',
            'color': 16711680,
            'gif': '',
        }

        # Determina status legível (ex.: exited -> stopped)
        state_raw = (container_entry.get('State') or container_entry.get('Status') or 'missing').lower()
        # Preserva 'paused' explicitamente para permitir allowlist
        if 'paused' in state_raw:
            state_norm = 'paused'
        elif any(x in state_raw for x in ['missing', 'exited', 'dead', 'created', 'stopped', 'removing']):
            state_norm = 'exited'
        else:
            state_norm = state_raw

        portainer_result = {
            'enabled': True,
            'verified': True,
            'running': False,
            'status': state_norm,
            'health': None,
            'endpoint_id': endpoint_id,
            'container_id': container_entry.get('Id'),
            'matched_name': container_name,
            'error': None,
        }

        # Supressão por estado (bloqueia reenvio até voltar a running)
        try:
            mapped_ip = enriched_info.get('real_ip')
            cid = container_entry.get('Id')
            key = build_container_key_by_id(mapped_ip, cid)
            current_state = 'down' if state_norm not in ['running', 'paused'] else state_norm
            
            # Passar portainer_client e endpoint_id para verificação blue/green
            should_send, reason = self.suppressor.should_send(
                key, current_state,
                container_name=container_name,
                portainer_client=portainer_client,
                endpoint_id=endpoint_id
            )
            if DEBUG_MODE:
                print(f"[DEBUG] PortainerMonitor: suppression check key={key} state={current_state} send={should_send} reason={reason}")
            if not should_send:
                return
        except Exception as exc:
            if DEBUG_MODE:
                print(f"[DEBUG] PortainerMonitor: erro na supressão por estado: {exc}")

        # Dedupe (pula se estiver no allowlist de "sempre notificar")
        fp = build_alert_fingerprint('container', alert_data['labels'], enriched_info, alert_status='firing')
        cname_norm = (container_name or '').strip().lower()
        always_notify = cname_norm in {n.strip().lower() for n in CONTAINER_ALWAYS_NOTIFY_ALLOWLIST}
        if ALERT_DEDUP_ENABLED and not always_notify:
            if self.dedupe_cache.is_within_ttl(fp):
                if DEBUG_MODE:
                    print(f"[DEBUG] PortainerMonitor: alerta suprimido por dedupe: {fp}")
                return
            self.dedupe_cache.touch(fp)

        content = format_container_alert(
            alert_data,
            enriched_info,
            alert_data['labels'],
            alert_data['values'],
            alert_data['status'],
            alert_data['annotations']['description'],
            severity_config,
            lambda v, s, t, d=False: 0,  # métrica fixa 0 (down)
            portainer_result=portainer_result,
        )

        embed = {
            'color': severity_config['color'],
            'fields': [
                {
                    'name': '📊 Detalhes Técnicos',
                    'value': f"**Alert:** {alert_data['labels']['alertname']}\n**Severidade:** {severity_config['label']}",
                    'inline': True,
                },
                {
                    'name': '🔁 Portainer',
                    'value': f"🔴 Estado: `{state_norm}`\n📛 Nome: `{container_name}`",
                    'inline': True,
                },
            ],
        }

        if DEBUG_MODE:
            print(f"[DEBUG] PortainerMonitor: enviando alerta de DOWN para {container_name} (endpoint {endpoint_id})")

        send_discord_payload(content=content, embeds=[embed])


def start_portainer_monitor(dedupe_cache: TTLCache):
    if not (PORTAINER_ACTIVE_MONITOR and portainer_client.enabled):
        if DEBUG_MODE:
            print("[DEBUG] PortainerMonitor não iniciado (desativado ou client indisponível)")
        return None
    monitor = PortainerMonitor(dedupe_cache)
    monitor.start()
    return monitor
