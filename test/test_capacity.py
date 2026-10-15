import unittest
from unittest.mock import Mock, patch

from app.capacity import capacity_lines


class CapacityTests(unittest.TestCase):
    def test_disk_capacity(self):
        lines = capacity_lines('disk', {'available_bytes': str(1024**4), 'total_bytes': str(10 * 1024**4)})
        self.assertIn('**Disponível:** 1.00 TiB', lines)
        self.assertIn('**Disponível (%):** 10.00%', lines)

    def test_missing_and_invalid_not_zero(self):
        for value in (None, '', 'NaN', 'inf', '-1', '{{ $values.D.Value }}', True):
            with self.subTest(value=value):
                self.assertIn('indisponível', capacity_lines('memory', {'available_bytes': value})[0])
        self.assertEqual(capacity_lines('memory', {'available_bytes': 0}), ['**Disponível:** 0.00 B'])

    def test_inconsistent(self):
        self.assertIn('inconsistentes', capacity_lines('disk', {'available_bytes': 2, 'total_bytes': 1})[0])

    def test_cpu(self):
        self.assertIn('**Capacidade ociosa equivalente:** 1.60 de 16 CPUs lógicas', capacity_lines('cpu', {'cpu_idle_percent': 10, 'cpu_count': 16}))
        self.assertEqual(capacity_lines('cpu', {'cpu_idle_percent': 101}), [])
        self.assertEqual(capacity_lines('cpu', {}), [])
        self.assertEqual(capacity_lines('container', {'available_bytes': 123}), [])

    def test_webhook_messages(self):
        from app.controller import create_app
        with patch('app.controller.start_portainer_monitor'), patch('app.controller.ContainerSuppressor'), patch('app.controller.send_discord_payload', return_value=Mock(status_code=204)) as send:
            client = create_app().test_client()
            for kind in ('Disk', 'Memory', 'CPU'):
                with self.subTest(kind=kind):
                    response = client.post('/alert', json={'alerts': [{
                        'status': 'firing', 'labels': {'alertname': kind, 'instance': 'test:9100'},
                        'values': {'A': 90, 'C': 1},
                        'annotations': {'available_bytes': 1024**4, 'total_bytes': 10 * 1024**4, 'cpu_idle_percent': 10, 'cpu_count': 16},
                    }]})
                    self.assertEqual(response.status_code, 200)
                    payload = send.call_args.kwargs
                    expected = '1.60 de 16 CPUs' if kind == 'CPU' else '1.00 TiB'
                    self.assertIn(expected, payload['content'])
                    self.assertIn(expected, str(payload['embeds']))
                    self.assertIn('90.0%', payload['content'])


if __name__ == '__main__':
    unittest.main()
