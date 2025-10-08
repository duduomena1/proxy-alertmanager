#!/usr/bin/env python3
"""
Script para testar as melhorias no processamento de alertas
"""

import json
import sys
import os
import re

# Simula o JSON que você recebeu
test_json = {
    "receiver": "testes de webhook",
    "status": "resolved",
    "alerts": [
        {
            "status": "resolved",
            "labels": {
                "alertname": "Disk app-001 - teste no data",
                "device": "/dev/mapper/app01--vg-root",
                "disk": "Caution",
                "fstype": "ext4",
                "grafana_folder": "Alerts",
                "instance": "node-exporter:9100",
                "job": "node-exporter",
                "mountpoint": "/"
            },
            "annotations": {
                "grafana_state_reason": "Updated",
                "summary": "TESTE TESTE TESTE TESTE TESTE"
            },
            "startsAt": "2025-10-08T14:33:30Z",
            "endsAt": "2025-10-08T16:29:55.933582749Z",
            "values": None,
            "valueString": "[ var='A' labels={device=/dev/mapper/app01--vg-root, fstype=ext4, instance=node-exporter:9100, job=node-exporter, mountpoint=/} value=16.002551672152055 ], [ var='C' labels={device=/dev/mapper/app01--vg-root, fstype=ext4, instance=node-exporter:9100, job=node-exporter, mountpoint=/} value=1 ]"
        }
    ]
}

def extract_real_ip_and_source(labels):
    """Testa a extração de IP e fonte"""
    
    real_ip = None
    prometheus_source = "unknown"
    original_instance = labels.get('instance', 'N/A')
    
    # 1. Identificar fonte do Prometheus
    if labels.get('prometheus'):
        prometheus_source = labels['prometheus']
    elif labels.get('prometheus_replica'):
        prometheus_source = labels['prometheus_replica']
    elif labels.get('receive'):
        prometheus_source = labels['receive']
    
    # 2. Buscar IP real
    ip_candidates = [
        labels.get('__address__'),
        labels.get('instance'),
        labels.get('kubernetes_node'),
        labels.get('host'),
        labels.get('hostname')
    ]
    
    for candidate in ip_candidates:
        if candidate and candidate != 'N/A':
            # Extrair IP se estiver no formato IP:porta
            ip_match = re.match(r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', candidate)
            if ip_match:
                real_ip = ip_match.group(1)
                break
            elif not candidate.startswith('node-exporter') and ':' in candidate:
                real_ip = candidate.split(':')[0]
                break
    
    return {
        'real_ip': real_ip,
        'prometheus_source': prometheus_source,
        'original_instance': original_instance,
        'clean_host': real_ip if real_ip else original_instance.split(':')[0] if ':' in original_instance else original_instance
    }

def extract_metric_value_enhanced(values, value_string):
    """Testa a extração de valores"""
    
    # Primeiro tenta dos values
    if values and isinstance(values, dict):
        for key in ['A', 'C', 'B', 'D']:
            if key in values and values[key] is not None:
                try:
                    return float(values[key])
                except (ValueError, TypeError):
                    continue
    
    # Fallback: extrair do valueString
    if value_string:
        try:
            # Padrão específico: "value=16.002551672152055"
            value_match = re.search(r'value=([0-9]*\.?[0-9]+)', str(value_string))
            if value_match:
                return float(value_match.group(1))
                
        except (ValueError, AttributeError):
            pass
    
    return 0.0

def test_improvements():
    """Testa as melhorias implementadas"""
    
    print("=" * 70)
    print("🧪 TESTE DAS MELHORIAS IMPLEMENTADAS")
    print("=" * 70)
    
    for alert in test_json['alerts']:
        labels = alert['labels']
        values = alert.get('values')
        value_string = alert.get('valueString', '')
        
        print(f"\n📊 DADOS ORIGINAIS:")
        print(f"Instance: {labels.get('instance')}")
        print(f"Values: {values}")
        print(f"ValueString: {value_string[:100]}...")
        
        print(f"\n🔍 APÓS MELHORIAS:")
        
        # Teste de extração de IP
        ip_info = extract_real_ip_and_source(labels)
        print(f"IP Real: {ip_info['real_ip']}")
        print(f"Host Limpo: {ip_info['clean_host']}")
        print(f"Prometheus Source: {ip_info['prometheus_source']}")
        print(f"Instance Original: {ip_info['original_instance']}")
        
        # Teste de extração de valor
        metric_value = extract_metric_value_enhanced(values, value_string)
        print(f"Valor Extraído: {metric_value}%")
        
        print(f"\n✅ RESULTADOS:")
        print(f"- IP identificado: {'❌ NÃO' if not ip_info['real_ip'] else '✅ SIM'}")
        print(f"- Valor extraído: {'❌ FALHOU' if metric_value == 0.0 else f'✅ {metric_value}%'}")
        print(f"- Host limpo: {ip_info['clean_host']}")
        
        # Simula o template
        print(f"\n📝 TEMPLATE RESULTANTE:")
        print(f"alertname: Disk Alert - {ip_info['clean_host']}")
        print(f"instance: {ip_info['clean_host']}")
        if ip_info['real_ip']:
            print(f"real_ip: {ip_info['real_ip']}")
        print(f"prometheus_source: {ip_info['prometheus_source']}")
        print(f"metric_value: {metric_value}")
        print(f"severity: {'high' if metric_value >= 90.0 else 'medium' if metric_value >= 80.0 else 'low'}")
        print(f"description: Disk usage is {metric_value:.1f}% on device {labels.get('device')} at server {ip_info['clean_host']}")
    
    print(f"\n" + "=" * 70)
    print("📋 ANÁLISE DOS PROBLEMAS ORIGINAIS:")
    print("=" * 70)
    
    print("❌ PROBLEMA 1: IP Real Perdido")
    print(f"   Antes: node-exporter:9100")
    print(f"   Depois: {ip_info['clean_host']} (melhorado mas ainda sem IP real)")
    print(f"   Solução: Adicionar __address__ label no Prometheus config")
    
    print("\n✅ PROBLEMA 2: Valores Perdidos")
    print(f"   Antes: values=null → 0.0%")
    print(f"   Depois: extraído do valueString → {metric_value}%")
    
    print("\n⚠️ PROBLEMA 3: Contexto de Origem")
    print(f"   Antes: Não identificava fonte")
    print(f"   Depois: prometheus_source = {ip_info['prometheus_source']}")
    print(f"   Nota: Precisa configurar labels no Prometheus")

if __name__ == '__main__':
    test_improvements()