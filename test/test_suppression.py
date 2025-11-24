#!/usr/bin/env python3
import unittest

from app.suppression import ContainerSuppressor

class TestContainerSuppressor(unittest.TestCase):
    def test_restart_loop_suppressed_until_running(self):
        s = ContainerSuppressor(ttl_seconds=60*60, enabled=True)
        key = '10.0.0.1|nginx'

        # Primeiro evento: restarting -> deve enviar
        send, reason = s.should_send(key, 'restarting', container_name='nginx')
        self.assertTrue(send, f"esperado enviar no primeiro restarting, razão={reason}")

        # Segundo evento: restarting -> não deve enviar
        send, reason = s.should_send(key, 'restarting', container_name='nginx')
        self.assertFalse(send, "deve suprimir enquanto não voltar a running")

        # Transição para running -> reseta
        send, reason = s.should_send(key, 'running', container_name='nginx')
        self.assertFalse(send, "não envia no running e reseta supressão")

        # Voltou a restarting -> deve enviar novamente
        send, reason = s.should_send(key, 'restarting', container_name='nginx')
        self.assertTrue(send, "deve enviar novamente após running")

    def test_paused_allowlist(self):
        # Mesmo sem ajustar env, lógica de allowlist é aplicada via nome passado
        s = ContainerSuppressor(ttl_seconds=60*60, enabled=True)
        key = '10.0.0.2|batch-paused'

        # paused permitido via allowlist simulada: passamos nome e dependemos da lista global, mas aqui apenas valida fluxo
        # Supondo que ALLOWLIST está populada fora, consideramos que a lógica evita alertar no paused e não ativa supressão
        send, reason = s.should_send(key, 'paused', container_name='batch-paused')
        self.assertFalse(send, "paused allowlisted não deve alertar")

        # Depois se ficar down, é a primeira falha -> deve enviar
        send, reason = s.should_send(key, 'down', container_name='batch-paused')
        # Pode enviar dependendo se paused não ativou supressão
        self.assertTrue(send, "primeira falha após paused deve alertar")

    def test_blue_green_sibling_active_suppresses_alert(self):
        """Testa que alerta é suprimido quando sibling blue/green está ativo"""
        from unittest.mock import Mock
        
        s = ContainerSuppressor(ttl_seconds=60*60, enabled=True)
        key = '10.0.0.3|app-blue'
        
        # Mock do Portainer client retornando sibling ativo
        mock_portainer = Mock()
        mock_portainer.list_containers.return_value = [
            {'Names': ['/app-green'], 'State': 'running', 'Id': 'abc123'}
        ]
        
        # Container app-blue caiu, mas app-green está running -> deve suprimir
        send, reason = s.should_send(
            key, 'down', 
            container_name='app-blue',
            portainer_client=mock_portainer,
            endpoint_id=15
        )
        self.assertFalse(send, "deve suprimir quando sibling está ativo")
        self.assertIn('blue_green_sibling_active', reason)
    
    def test_blue_green_both_down_sends_alerts(self):
        """Testa que alertas são enviados quando ambos os containers do par caem"""
        from unittest.mock import Mock
        
        s = ContainerSuppressor(ttl_seconds=60*60, enabled=True)
        
        # Mock do Portainer client retornando sibling também down
        mock_portainer = Mock()
        mock_portainer.list_containers.return_value = [
            {'Names': ['/app-green'], 'State': 'exited', 'Id': 'abc123'}
        ]
        
        # Primeiro container (app-blue) cai
        key_blue = '10.0.0.3|app-blue'
        send, reason = s.should_send(
            key_blue, 'down',
            container_name='app-blue',
            portainer_client=mock_portainer,
            endpoint_id=15
        )
        self.assertTrue(send, "deve enviar alerta quando sibling também está down")
        
        # Segundo container (app-green) também cai
        key_green = '10.0.0.3|app-green'
        mock_portainer.list_containers.return_value = [
            {'Names': ['/app-blue'], 'State': 'down', 'Id': 'def456'}
        ]
        send, reason = s.should_send(
            key_green, 'down',
            container_name='app-green',
            portainer_client=mock_portainer,
            endpoint_id=15
        )
        self.assertTrue(send, "deve enviar alerta quando ambos estão down")
    
    def test_blue_green_naming_variations(self):
        """Testa detecção de diferentes variações de nomenclatura blue/green"""
        from app.suppression import extract_blue_green_base
        
        # Teste com hífen
        base, color = extract_blue_green_base('nginx-blue')
        self.assertEqual(base, 'nginx')
        self.assertEqual(color, 'blue')
        
        # Teste com underscore
        base, color = extract_blue_green_base('api_green')
        self.assertEqual(base, 'api')
        self.assertEqual(color, 'green')
        
        # Teste case-insensitive
        base, color = extract_blue_green_base('WORKER-BLUE')
        self.assertEqual(base, 'worker')
        self.assertEqual(color, 'blue')
        
        # Teste com uppercase underscore
        base, color = extract_blue_green_base('APP_GREEN')
        self.assertEqual(base, 'app')
        self.assertEqual(color, 'green')
        
        # Teste container sem padrão blue/green
        base, color = extract_blue_green_base('nginx')
        self.assertIsNone(base)
        self.assertIsNone(color)
        
        # Teste com padrão não blue/green (v1/v2)
        base, color = extract_blue_green_base('app-v1')
        self.assertIsNone(base)
        self.assertIsNone(color)
    
    def test_blue_green_disabled(self):
        """Testa que supressão blue/green respeita a flag BLUE_GREEN_SUPPRESSION_ENABLED"""
        from unittest.mock import Mock, patch
        
        s = ContainerSuppressor(ttl_seconds=60*60, enabled=True)
        key = '10.0.0.3|app-blue'
        
        mock_portainer = Mock()
        mock_portainer.list_containers.return_value = [
            {'Names': ['/app-green'], 'State': 'running', 'Id': 'abc123'}
        ]
        
        # Desabilitar blue/green suppression
        with patch('app.suppression.BLUE_GREEN_SUPPRESSION_ENABLED', False):
            # Container app-blue caiu, mas blue/green está desabilitado -> deve enviar
            send, reason = s.should_send(
                key, 'down',
                container_name='app-blue',
                portainer_client=mock_portainer,
                endpoint_id=15
            )
            self.assertTrue(send, "deve enviar quando blue/green suppression está desabilitado")
    
    def test_blue_green_without_portainer(self):
        """Testa que blue/green não afeta quando Portainer não está disponível"""
        s = ContainerSuppressor(ttl_seconds=60*60, enabled=True)
        key = '10.0.0.3|app-blue'
        
        # Sem Portainer client -> deve enviar alerta normalmente (primeira falha)
        send, reason = s.should_send(
            key, 'down',
            container_name='app-blue',
            portainer_client=None,
            endpoint_id=None
        )
        self.assertTrue(send, "deve enviar alerta quando Portainer não está disponível")

if __name__ == '__main__':
    unittest.main()
