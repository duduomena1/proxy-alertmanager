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

if __name__ == '__main__':
    unittest.main()
