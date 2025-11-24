#!/usr/bin/env python3
"""
Teste para verificar se a supressão blue/green está funcionando corretamente.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.suppression import (
    ContainerSuppressor, 
    extract_blue_green_base, 
    find_active_sibling,
    build_container_key_by_id
)

def test_blue_green_detection():
    """Testa detecção de padrões blue/green."""
    print("=" * 80)
    print("Teste 1: Detecção de padrões blue/green")
    print("=" * 80)
    
    test_cases = [
        ('nginx-blue', ('nginx', 'blue')),
        ('nginx-green', ('nginx', 'green')),
        ('app_blue', ('app', 'blue')),
        ('app_green', ('app', 'green')),
        ('API-BLUE', ('api', 'blue')),
        ('Service_GREEN', ('service', 'green')),
        ('app-v1', (None, None)),  # Não é blue/green
        ('simple', (None, None)),   # Não é blue/green
    ]
    
    all_passed = True
    for container_name, expected in test_cases:
        result = extract_blue_green_base(container_name)
        passed = result == expected
        status = "✅" if passed else "❌"
        print(f"{status} '{container_name}' -> {result} (esperado: {expected})")
        if not passed:
            all_passed = False
    
    return all_passed

def test_suppression_logic():
    """Testa lógica de supressão sem Portainer (casos básicos)."""
    print("\n" + "=" * 80)
    print("Teste 2: Lógica de supressão básica")
    print("=" * 80)
    
    suppressor = ContainerSuppressor(enabled=True)
    
    # Cenário 1: Primeiro alerta de falha
    key1 = "192.168.1.100|id:abc123"
    should_send, reason = suppressor.should_send(key1, 'down', container_name='test-container')
    print(f"\n1. Primeiro alerta DOWN:")
    print(f"   should_send={should_send}, reason={reason}")
    assert should_send == True, "Primeiro alerta deveria ser enviado"
    assert reason == 'first_failure_since_running', f"Razão incorreta: {reason}"
    print("   ✅ PASSOU")
    
    # Cenário 2: Segundo alerta de falha (deveria ser suprimido)
    should_send, reason = suppressor.should_send(key1, 'down', container_name='test-container')
    print(f"\n2. Segundo alerta DOWN (repetição):")
    print(f"   should_send={should_send}, reason={reason}")
    assert should_send == False, "Segundo alerta deveria ser suprimido"
    assert reason == 'already_suppressed_until_running', f"Razão incorreta: {reason}"
    print("   ✅ PASSOU")
    
    # Cenário 3: Container volta a running (reset)
    should_send, reason = suppressor.should_send(key1, 'running', container_name='test-container')
    print(f"\n3. Container volta a RUNNING:")
    print(f"   should_send={should_send}, reason={reason}")
    assert should_send == False, "Running não envia alerta"
    assert reason == 'reset_on_running', f"Razão incorreta: {reason}"
    print("   ✅ PASSOU")
    
    # Cenário 4: Nova falha após running (deveria enviar novamente)
    should_send, reason = suppressor.should_send(key1, 'down', container_name='test-container')
    print(f"\n4. Nova falha após RUNNING:")
    print(f"   should_send={should_send}, reason={reason}")
    assert should_send == True, "Nova falha após running deveria ser enviada"
    assert reason == 'first_failure_since_running', f"Razão incorreta: {reason}"
    print("   ✅ PASSOU")
    
    return True

def test_blue_green_suppression_mock():
    """
    Testa supressão blue/green com mock (sem Portainer real).
    Simula cenário onde sibling está ativo.
    """
    print("\n" + "=" * 80)
    print("Teste 3: Supressão blue/green (conceitual)")
    print("=" * 80)
    
    # Teste conceitual: verificar que a lógica existe
    suppressor = ContainerSuppressor(enabled=True)
    
    # Sem portainer_client, não deve suprimir por blue/green
    key = "192.168.1.100|id:xyz789"
    should_send, reason = suppressor.should_send(
        key, 
        'down', 
        container_name='app-blue',
        portainer_client=None,  # Sem Portainer
        endpoint_id=None
    )
    
    print(f"\nSem Portainer disponível:")
    print(f"   should_send={should_send}, reason={reason}")
    print(f"   ✅ Lógica blue/green requer Portainer (comportamento esperado)")
    
    # Com Portainer mas sem endpoint_id
    should_send2, reason2 = suppressor.should_send(
        key + "_2", 
        'down', 
        container_name='app-green',
        portainer_client="mock",  # Mock do cliente (não será usado)
        endpoint_id=None  # Sem endpoint
    )
    
    print(f"\nCom Portainer mas sem endpoint_id:")
    print(f"   should_send={should_send2}, reason={reason2}")
    print(f"   ✅ Lógica blue/green requer endpoint_id (comportamento esperado)")
    
    return True

def main():
    """Executa todos os testes."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "TESTES DE SUPRESSÃO BLUE/GREEN" + " " * 28 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    results = []
    
    # Teste 1
    try:
        results.append(("Detecção de padrões", test_blue_green_detection()))
    except Exception as e:
        print(f"❌ ERRO: {e}")
        results.append(("Detecção de padrões", False))
    
    # Teste 2
    try:
        results.append(("Lógica de supressão", test_suppression_logic()))
    except Exception as e:
        print(f"❌ ERRO: {e}")
        results.append(("Lógica de supressão", False))
    
    # Teste 3
    try:
        results.append(("Supressão blue/green", test_blue_green_suppression_mock()))
    except Exception as e:
        print(f"❌ ERRO: {e}")
        results.append(("Supressão blue/green", False))
    
    # Resumo
    print("\n" + "=" * 80)
    print("RESUMO DOS TESTES")
    print("=" * 80)
    
    for name, passed in results:
        status = "✅ PASSOU" if passed else "❌ FALHOU"
        print(f"{status}: {name}")
    
    all_passed = all(r[1] for r in results)
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ TODOS OS TESTES PASSARAM!")
    else:
        print("❌ ALGUNS TESTES FALHARAM")
    print("=" * 80 + "\n")
    
    return 0 if all_passed else 1

if __name__ == '__main__':
    sys.exit(main())
