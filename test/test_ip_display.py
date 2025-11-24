#!/usr/bin/env python3
"""
Teste para verificar se o IP está sendo extraído e exibido corretamente
nos alertas de container.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.enrichment import extract_real_ip_and_source
from app.formatters import format_container_alert, extract_container_info
from app.detection import get_severity_config
from app.utils import extract_metric_value_enhanced

def test_container_alert_ip_display():
    """
    Testa diferentes cenários de alertas de container para garantir
    que o IP seja exibido corretamente.
    """
    
    # Cenário 1: Alert do Grafana sem host_ip (problema reportado)
    print("=" * 80)
    print("Cenário 1: Alert do Grafana sem host_ip")
    print("=" * 80)
    
    labels1 = {
        'alertname': 'Container Status Alert - nginx-server',
        'container': 'nginx',
        'instance': '192.168.1.100:9100',
        'job': 'docker-nginx',
        'severity': 'critical'
    }
    
    alert_data1 = {
        'status': 'firing',
        'startsAt': '2025-10-03T16:00:00Z',
        'values': {'A': 0, 'C': 1},
        'valueString': '[ var=\'A\' labels={container=nginx, instance=192.168.1.100:9100, job=docker-nginx} value=0 ]'
    }
    
    enriched_info1 = extract_real_ip_and_source(labels1)
    print(f"\nLabels: {labels1}")
    print(f"Enriched info: {enriched_info1}")
    
    description1 = "🐳 Container nginx no servidor 192.168.1.100 está OFFLINE"
    severity_config1 = get_severity_config('critical', 'container')
    
    def get_metric_value_mock(values, value_string, alert_type, debug_mode):
        return extract_metric_value_enhanced(values, value_string, alert_type, debug_mode)
    
    content1 = format_container_alert(
        alert_data1,
        enriched_info1,
        labels1,
        alert_data1['values'],
        'firing',
        description1,
        severity_config1,
        get_metric_value_mock,
        portainer_result=None
    )
    
    print("\n" + "─" * 80)
    print("RESULTADO DO ALERTA:")
    print("─" * 80)
    print(content1)
    print("\n")
    
    # Verifica se o IP está presente
    if '192.168.1.100' in content1:
        print("✅ IP encontrado no alerta!")
    else:
        print("❌ IP NÃO encontrado no alerta!")
    
    # Cenário 2: Alert do Prometheus com host_ip
    print("\n" + "=" * 80)
    print("Cenário 2: Alert do Prometheus com host_ip")
    print("=" * 80)
    
    labels2 = {
        'alertname': 'Container Status Alert - db-server',
        'container': 'postgres',
        'instance': '172.16.104.12:9100',
        'host_ip': '172.16.104.12',
        'real_host': '172.16.104.12:9100',
        'job': 'docker-postgres',
        'severity': 'critical'
    }
    
    alert_data2 = {
        'status': 'firing',
        'startsAt': '2025-10-03T16:00:00Z',
        'values': {'A': 0, 'C': 1},
        'valueString': '[ var=\'A\' labels={container=postgres, instance=172.16.104.12:9100, job=docker-postgres} value=0 ]'
    }
    
    enriched_info2 = extract_real_ip_and_source(labels2)
    print(f"\nLabels: {labels2}")
    print(f"Enriched info: {enriched_info2}")
    
    description2 = "🐳 Container postgres no servidor 172.16.104.12 está OFFLINE"
    
    content2 = format_container_alert(
        alert_data2,
        enriched_info2,
        labels2,
        alert_data2['values'],
        'firing',
        description2,
        severity_config1,
        get_metric_value_mock,
        portainer_result=None
    )
    
    print("\n" + "─" * 80)
    print("RESULTADO DO ALERTA:")
    print("─" * 80)
    print(content2)
    print("\n")
    
    # Verifica se o IP está presente
    if '172.16.104.12' in content2:
        print("✅ IP encontrado no alerta!")
    else:
        print("❌ IP NÃO encontrado no alerta!")
    
    # Cenário 3: Alert com hostname
    print("\n" + "=" * 80)
    print("Cenário 3: Alert com hostname")
    print("=" * 80)
    
    labels3 = {
        'alertname': 'Container Status Alert - app-server',
        'container': 'app',
        'instance': 'app01-focorj:9100',
        'job': 'docker-app',
        'severity': 'warning'
    }
    
    alert_data3 = {
        'status': 'firing',
        'startsAt': '2025-10-03T16:00:00Z',
        'values': {'A': 0, 'C': 1},
        'valueString': '[ var=\'A\' labels={container=app, instance=app01-focorj:9100, job=docker-app} value=0 ]'
    }
    
    enriched_info3 = extract_real_ip_and_source(labels3)
    print(f"\nLabels: {labels3}")
    print(f"Enriched info: {enriched_info3}")
    
    description3 = "🐳 Container app no servidor app01-focorj está OFFLINE"
    severity_config3 = get_severity_config('warning', 'container')
    
    content3 = format_container_alert(
        alert_data3,
        enriched_info3,
        labels3,
        alert_data3['values'],
        'firing',
        description3,
        severity_config3,
        get_metric_value_mock,
        portainer_result=None
    )
    
    print("\n" + "─" * 80)
    print("RESULTADO DO ALERTA:")
    print("─" * 80)
    print(content3)
    print("\n")
    
    # Verifica se o hostname está presente
    if 'app01-focorj' in content3:
        print("✅ Hostname encontrado no alerta!")
    else:
        print("❌ Hostname NÃO encontrado no alerta!")

if __name__ == '__main__':
    test_container_alert_ip_display()
