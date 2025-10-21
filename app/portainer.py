import json
import os
import time
from typing import Dict, Iterable, List, Optional, Any

import requests
import urllib3
import warnings

from .constants import (
    CONTAINER_VALIDATE_WITH_PORTAINER,
    PORTAINER_API_KEY,
    PORTAINER_BASE_URL,
    PORTAINER_ENDPOINT_MAP_FILE,
    PORTAINER_FAIL_OPEN,
    PORTAINER_STRICT_NAME_MATCH,
    PORTAINER_TIMEOUT_SECONDS,
    PORTAINER_VERIFY_TLS,
    DEBUG_MODE,
)

# Suprime globalmente avisos de HTTPS não verificado quando TLS estiver desativado para Portainer
if not PORTAINER_VERIFY_TLS:
    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        # Alguns ambientes usam o pacote urllib3 dentro de requests
        requests.packages.urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  # type: ignore[attr-defined]
        if DEBUG_MODE:
            print("[DEBUG] Avisos globais de InsecureRequestWarning desabilitados (PORTAINER_VERIFY_TLS=false)")
    except Exception:
        pass


def _normalize_name(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    return name.strip().lstrip('/').lower()


def _load_endpoint_map(file_path: Optional[str]) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    if not file_path:
        return mapping

    if not os.path.exists(file_path):
        if DEBUG_MODE:
            print(f"[DEBUG] Portainer endpoint map file não encontrado: {file_path}")
        return mapping

    try:
        with open(file_path, 'r', encoding='utf-8') as fp:
            raw = fp.read()
    except Exception as exc:
        if DEBUG_MODE:
            print(f"[DEBUG] Falha ao ler Portainer endpoint map: {exc}")
        return mapping

    raw = raw.strip()
    if not raw:
        return mapping

    # Tenta JSON primeiro
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            for key, value in data.items():
                try:
                    if isinstance(value, dict):
                        # formato estendido: { "host": {"id": 4, "ssh_user": "ubuntu"} }
                        mapping[key.lower()] = int(value.get("id"))
                    else:
                        mapping[key.lower()] = int(value)
                except (TypeError, ValueError):
                    if DEBUG_MODE:
                        print(f"[DEBUG] Endpoint map value inválido para '{key}': {value}")
            return mapping
    except json.JSONDecodeError:
        pass

    # Fallback simples estilo "host: endpoint"
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        key = key.strip().lower()
        try:
            mapping[key] = int(value.strip())
        except ValueError:
            if DEBUG_MODE:
                print(f"[DEBUG] Endpoint map value inválido para '{key}': {value}")
    return mapping


def _load_endpoint_meta(file_path: Optional[str]) -> Dict[str, Dict[str, Any]]:
    meta: Dict[str, Dict[str, Any]] = {}
    if not file_path or not os.path.exists(file_path):
        return meta
    try:
        with open(file_path, 'r', encoding='utf-8') as fp:
            data = json.load(fp)
    except Exception:
        return meta
    if not isinstance(data, dict):
        return meta
    for key, value in data.items():
        if isinstance(value, dict):
            info: Dict[str, Any] = {}
            if 'ssh_user' in value and value['ssh_user']:
                info['ssh_user'] = str(value['ssh_user'])
            if info:
                meta[key.lower()] = info
    return meta


class PortainerClient:
    def __init__(self):
        self.enabled = (
            CONTAINER_VALIDATE_WITH_PORTAINER
            and PORTAINER_BASE_URL
            and PORTAINER_API_KEY
        )
        self.base_url = PORTAINER_BASE_URL.rstrip('/') if PORTAINER_BASE_URL else None
        self.api_key = PORTAINER_API_KEY
        self.timeout = PORTAINER_TIMEOUT_SECONDS
        self.verify_tls = PORTAINER_VERIFY_TLS
        self.fail_open = PORTAINER_FAIL_OPEN
        self.strict_name_match = PORTAINER_STRICT_NAME_MATCH
        self.endpoint_map_path = PORTAINER_ENDPOINT_MAP_FILE
        self.endpoint_map = _load_endpoint_map(self.endpoint_map_path)
        self.endpoint_meta = _load_endpoint_meta(self.endpoint_map_path)
        try:
            self._map_mtime = os.path.getmtime(self.endpoint_map_path) if self.endpoint_map_path and os.path.exists(self.endpoint_map_path) else 0.0
        except Exception:
            self._map_mtime = 0.0
        self._endpoints_cache: Dict[int, Dict] = {}
        self._last_refresh = 0.0

        # Suprime avisos de HTTPS inseguro quando a verificação TLS está desativada
        if self.enabled and not self.verify_tls:
            try:
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                if DEBUG_MODE:
                    print("[DEBUG] Avisos de InsecureRequestWarning desabilitados (PORTAINER_VERIFY_TLS=false)")
            except Exception:
                # Fallback silencioso caso urllib3 não esteja disponível por algum motivo
                pass

        if self.enabled and DEBUG_MODE:
            print("[DEBUG] PortainerClient habilitado")
            if self.endpoint_map:
                print(f"[DEBUG] Portainer endpoint_map carregado ({len(self.endpoint_map)} chaves): {list(self.endpoint_map.keys())[:10]}{'...' if len(self.endpoint_map)>10 else ''}")

    # ---------- Setup helpers ----------

    def _headers(self) -> Dict[str, str]:
        return {
            "X-API-Key": self.api_key,
            "Accept": "application/json",
        }

    def _request(self, method: str, path: str, params: Optional[Dict] = None) -> requests.Response:
        if not self.base_url:
            raise RuntimeError("Portainer BASE_URL não configurado")
        url = f"{self.base_url}{path}"
        resp = requests.request(
            method,
            url,
            headers=self._headers(),
            params=params,
            timeout=self.timeout,
            verify=self.verify_tls,
        )
        resp.raise_for_status()
        return resp

    def _ensure_endpoints_cache(self) -> None:
        if not self.enabled:
            return
        now = time.time()
        if self._endpoints_cache and (now - self._last_refresh) < 60:
            return
        try:
            resp = self._request("GET", "/endpoints")
            data = resp.json()
            if isinstance(data, list):
                self._endpoints_cache = {item["Id"]: item for item in data if "Id" in item}
                # também index por nome para fallback
                self._endpoint_name_map = {
                    str(item.get("Name", "")).lower(): item["Id"]
                    for item in data
                    if "Id" in item
                }
                self._last_refresh = now
                if DEBUG_MODE:
                    def _ep_info(it: Dict) -> str:
                        name = it.get('Name','?')
                        eid = it.get('Id','?')
                        pub = it.get('PublicURL') or ''
                        url = it.get('URL') or ''
                        extra = pub or url
                        extra = f" -> {extra}" if extra else ""
                        return f"{name}({eid}){extra}"
                    summary = ", ".join([_ep_info(it) for it in data])
                    print(f"[DEBUG] Portainer endpoints descobertos: {summary}")
        except Exception as exc:
            if DEBUG_MODE:
                print(f"[DEBUG] Falha ao atualizar cache de endpoints Portainer: {exc}")

    def list_endpoints(self) -> Dict[int, Dict]:
        """Retorna o cache de endpoints (Id->objeto). Atualiza se necessário."""
        self._maybe_reload_endpoint_map()
        self._ensure_endpoints_cache()
        return dict(self._endpoints_cache)

    def list_containers(self, endpoint_id: int, all: bool = False) -> List[Dict]:
        """Lista containers em um endpoint específico."""
        params = {'all': 1 if all else 0}
        resp = self._request("GET", f"/endpoints/{endpoint_id}/docker/containers/json", params=params)
        return resp.json() if resp.content else []

    # ---------- Public API ----------
    def get_host_for_endpoint(self, endpoint_id: int, prefer_ip: bool = True) -> Optional[str]:
        """Retorna uma chave (host/IP) do mapa que aponte para o endpoint_id.
        Se prefer_ip=True, tenta um IP primeiro; caso contrário, retorna a primeira chave encontrada.
        """
        if not self.endpoint_map:
            return None
        candidate_any = None
        import re
        for host, eid in self.endpoint_map.items():
            if eid == endpoint_id:
                if prefer_ip and re.match(r"^\d{1,3}(?:\.\d{1,3}){3}$", host):
                    return host
                if candidate_any is None:
                    candidate_any = host
        return candidate_any

    def resolve_endpoint(self, host: Optional[str]) -> Optional[int]:
        self._maybe_reload_endpoint_map()
        if not host:
            return None

        cleaned = host.split(':')[0].strip().lower()
        if not cleaned:
            return None

        self._ensure_endpoints_cache()

        # 1) Map file
        if cleaned in self.endpoint_map:
            return self.endpoint_map[cleaned]

        # tenta variantes simples (ex.: remove domínio)
        if '.' in cleaned:
            short = cleaned.split('.')[0]
            if short in self.endpoint_map:
                return self.endpoint_map[short]

        # 2) match por nome de endpoint (case insensitive)
        endpoint_name_map = getattr(self, "_endpoint_name_map", {})
        if cleaned in endpoint_name_map:
            return endpoint_name_map[cleaned]

        if '.' in cleaned:
            short = cleaned.split('.')[0]
            if short in endpoint_name_map:
                return endpoint_name_map[short]

        return None

    def _match_container_name(self, names: Iterable[str], candidates: Iterable[str]) -> Optional[str]:
        normalized_candidates = {_normalize_name(c) for c in candidates if c}
        normalized_candidates.discard(None)
        if not normalized_candidates:
            return None

        normalized_names = {_normalize_name(n) for n in names if n}
        normalized_names.discard(None)

        # Match exato
        for candidate in normalized_candidates:
            if candidate in normalized_names:
                return candidate

        if self.strict_name_match:
            return None

        # Fallback por prefixo/contain
        for name in normalized_names:
            for candidate in normalized_candidates:
                if candidate and name and (candidate in name or name in candidate):
                    return name

        return None

    def _collect_candidate_names(self, labels: Dict) -> List[str]:
        candidates = []
        keys = [
            'container',
            'container_name',
            'name',
            'pod',
            'pod_name',
            'service',
            'job',
        ]
        for key in keys:
            value = labels.get(key)
            if value:
                candidates.append(str(value))

        # Compose/Stack labels
        compose_service = labels.get('com.docker.compose.service') or labels.get('label_com_docker_compose_service')
        if compose_service:
            candidates.append(str(compose_service))

        stack_namespace = labels.get('com.docker.stack.namespace')
        if stack_namespace:
            candidates.append(str(stack_namespace))

        return candidates

    def verify_container(self, host: Optional[str], labels: Dict) -> Dict:
        """Retorna dict com informações da verificação via Portainer."""
        result = {
            'enabled': self.enabled,
            'verified': False,
            'running': None,
            'status': None,
            'health': None,
            'endpoint_id': None,
            'container_id': None,
            'matched_name': None,
            'error': None,
        }

        if not self.enabled:
            return result

        endpoint_id = self.resolve_endpoint(host)
        if endpoint_id is None:
            result['error'] = 'endpoint_not_found'
            if DEBUG_MODE:
                print(f"[DEBUG] Portainer: endpoint não encontrado para host '{host}'")
            return result

        candidates = self._collect_candidate_names(labels)
        if DEBUG_MODE:
            print(f"[DEBUG] Portainer candidatos de nome para {host}: {candidates}")

        try:
            running_resp = self._request(
                "GET",
                f"/endpoints/{endpoint_id}/docker/containers/json",
                params={'all': 0},
            )
            running_containers = running_resp.json() if running_resp.content else []
        except Exception as exc:
            result['error'] = f"api_error_running:{exc}"
            if DEBUG_MODE:
                print(f"[DEBUG] Portainer erro ao listar containers running: {exc}")
            return result if self.fail_open else result

        match_info = self._find_match_in_list(running_containers, candidates)
        if match_info:
            result.update(match_info)
            result['endpoint_id'] = endpoint_id
            result['verified'] = True
            result['running'] = True
            result['status'] = match_info.get('status') or 'running'
            return result

        # tenta all=1
        try:
            all_resp = self._request(
                "GET",
                f"/endpoints/{endpoint_id}/docker/containers/json",
                params={'all': 1},
            )
            all_containers = all_resp.json() if all_resp.content else []
        except Exception as exc:
            result['error'] = f"api_error_all:{exc}"
            if DEBUG_MODE:
                print(f"[DEBUG] Portainer erro ao listar containers all: {exc}")
            return result if self.fail_open else result

        match_info = self._find_match_in_list(all_containers, candidates)
        if not match_info:
            result['endpoint_id'] = endpoint_id
            result['verified'] = True
            result['running'] = False
            result['status'] = 'missing'
            return result

        result.update(match_info)
        result['endpoint_id'] = endpoint_id

        container_id = match_info.get('container_id')
        if not container_id:
            result['verified'] = True
            result['running'] = False
            result['status'] = match_info.get('status') or 'unknown'
            return result

        # Recupera detalhes completos
        try:
            inspect_resp = self._request(
                "GET",
                f"/endpoints/{endpoint_id}/docker/containers/{container_id}/json",
            )
            inspect_data = inspect_resp.json()
        except Exception as exc:
            result['error'] = f"api_error_inspect:{exc}"
            if DEBUG_MODE:
                print(f"[DEBUG] Portainer erro ao inspecionar container: {exc}")
            return result if self.fail_open else result

        state = inspect_data.get('State', {}) if isinstance(inspect_data, dict) else {}
        result['verified'] = True
        result['running'] = bool(state.get('Running'))
        result['status'] = state.get('Status') or match_info.get('status')
        health = state.get('Health', {}) if isinstance(state.get('Health'), dict) else {}
        result['health'] = health.get('Status')
        return result

    def _find_match_in_list(self, containers: Iterable[Dict], candidates: List[str]) -> Optional[Dict]:
        for entry in containers or []:
            names = entry.get('Names') or []
            match = self._match_container_name(names, candidates)
            if match:
                return {
                    'container_id': entry.get('Id'),
                    'matched_name': match,
                    'status': entry.get('State') or entry.get('Status'),
                }

            labels = entry.get('Labels', {}) or {}
            alt_names = [labels.get('com.docker.compose.service'), labels.get('io.kubernetes.container.name')]
            match = self._match_container_name(alt_names, candidates)
            if match:
                return {
                    'container_id': entry.get('Id'),
                    'matched_name': match,
                    'status': entry.get('State') or entry.get('Status'),
                }
        return None

    # ---------- Map reload ----------
    def _maybe_reload_endpoint_map(self) -> None:
        if not self.endpoint_map_path:
            return
        try:
            mtime = os.path.getmtime(self.endpoint_map_path) if os.path.exists(self.endpoint_map_path) else 0.0
        except Exception:
            return
        if mtime and mtime != getattr(self, "_map_mtime", 0.0):
            new_map = _load_endpoint_map(self.endpoint_map_path)
            new_meta = _load_endpoint_meta(self.endpoint_map_path)
            if new_map:
                self.endpoint_map = new_map
                self.endpoint_meta = new_meta
                self._map_mtime = mtime
                if DEBUG_MODE:
                    print(f"[DEBUG] Portainer endpoint_map recarregado ({len(self.endpoint_map)} chaves)")

    # ---------- Helpers públicos extra ----------
    def get_host_for_endpoint(self, endpoint_id: int, prefer_ip: bool = True) -> Optional[str]:
        """Retorna uma chave (host/IP) do mapa que aponte para o endpoint_id.
        Se prefer_ip=True, tenta um IP primeiro; caso contrário, retorna a primeira chave encontrada.
        """
        if not self.endpoint_map:
            return None
        candidate_any = None
        import re
        for host, eid in self.endpoint_map.items():
            if eid == endpoint_id:
                if prefer_ip and re.match(r"^\d{1,3}(?:\.\d{1,3}){3}$", host):
                    return host
                if candidate_any is None:
                    candidate_any = host
        return candidate_any

    def get_ssh_user_for_endpoint(self, endpoint_id: int, prefer_ip: bool = True) -> Optional[str]:
        """Retorna ssh_user associado ao endpoint_id, se definido no JSON (formato estendido)."""
        if not getattr(self, 'endpoint_meta', None):
            return None
        import re
        candidate_any = None
        for host, eid in self.endpoint_map.items():
            if eid == endpoint_id:
                meta = self.endpoint_meta.get(host.lower())
                if not meta:
                    continue
                user = meta.get('ssh_user')
                if not user:
                    continue
                if prefer_ip and re.match(r"^\d{1,3}(?:\.\d{1,3}){3}$", host):
                    return user
                candidate_any = candidate_any or user
        return candidate_any


portainer_client = PortainerClient()
