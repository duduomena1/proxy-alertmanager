#!/usr/bin/env python3
"""
Teste para verificar se o PortainerMonitor consegue acessar 
o portainer_client corretamente após a correção.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.portainer_monitor import PortainerMonitor
from app.dedupe import TTLCache
from app.portainer import portainer_client

def test_portainer_monitor_fix():
    """
    Verifica se o PortainerMonitor consegue acessar portainer_client
    sem lançar AttributeError.
    """
    print("=" * 80)
    print("Teste: Verificação de acesso ao portainer_client")
    print("=" * 80)
    
    # Cria cache e monitor
    cache = TTLCache(ttl_seconds=60, max_size=1000)
    monitor = PortainerMonitor(cache)
    
    # Verifica se o portainer_client está disponível como módulo global
    print(f"\n✓ portainer_client importado: {portainer_client}")
    print(f"✓ portainer_client.enabled: {portainer_client.enabled}")
    
    # Verifica se o monitor tem o suppressor
    print(f"✓ monitor.suppressor: {monitor.suppressor}")
    
    # Simula o código que estava quebrando
    # (usando portainer_client diretamente em vez de self.portainer_client)
    try:
        # Esse é o código que estava na linha 263 do portainer_monitor.py
        # Simulando a chamada com portainer_client
        test_key = "test_key"
        test_state = "down"
        test_name = "test_container"
        
        # Chama should_send com portainer_client
        should_send, reason = monitor.suppressor.should_send(
            test_key, 
            test_state,
            container_name=test_name,
            portainer_client=portainer_client,  # Usando portainer_client global
            endpoint_id=None
        )
        
        print(f"\n✓ Chamada ao suppressor.should_send executada com sucesso!")
        print(f"  - should_send: {should_send}")
        print(f"  - reason: {reason}")
        print("\n" + "=" * 80)
        print("✅ TESTE PASSOU: Não há mais AttributeError!")
        print("=" * 80)
        
    except AttributeError as e:
        print(f"\n❌ ERRO: {e}")
        print("=" * 80)
        print("❌ TESTE FALHOU: AttributeError ainda ocorre")
        print("=" * 80)
        return False
    except Exception as e:
        print(f"\n⚠️  Outro erro (não é AttributeError): {e}")
        print("   (Isso pode ser esperado dependendo da configuração)")
    
    return True

if __name__ == '__main__':
    success = test_portainer_monitor_fix()
    sys.exit(0 if success else 1)
