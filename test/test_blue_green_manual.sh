#!/bin/bash
# Script de teste manual para validar supressão blue/green

echo "=== TESTE MANUAL: Supressão Blue/Green ==="
echo ""
echo "Pré-requisitos:"
echo "  1. Portainer configurado e acessível"
echo "  2. CONTAINER_VALIDATE_WITH_PORTAINER=true"
echo "  3. BLUE_GREEN_SUPPRESSION_ENABLED=true (padrão)"
echo ""
echo "Cenários de teste:"
echo ""
echo "CENÁRIO 1: Container blue cai, green está ativo"
echo "  - Expectativa: Alerta é SUPRIMIDO"
echo "  - Motivo: 'blue_green_sibling_active:app-green'"
echo ""

cat <<'EOF' > /tmp/test_blue_down_green_up.json
{
  "receiver": "discord",
  "status": "firing",
  "alerts": [{
    "status": "firing",
    "labels": {
      "alertname": "Container Status Alert - app-blue",
      "container": "app-blue",
      "instance": "192.168.1.100:9100",
      "job": "docker-monitor"
    },
    "annotations": {
      "description": "Container app-blue está DOWN",
      "summary": "app-blue parou"
    },
    "startsAt": "2025-11-24T12:00:00Z",
    "endsAt": "0001-01-01T00:00:00Z",
    "values": {
      "A": 0
    },
    "valueString": "value=0"
  }]
}
EOF

echo "Comando para testar (ajuste o IP/endpoint conforme seu ambiente):"
echo "curl -X POST http://localhost:5001/webhook/grafana \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d @/tmp/test_blue_down_green_up.json"
echo ""
echo "Verifique nos logs se aparece:"
echo "  'Suprimindo alerta de app-blue: sibling app-green está ativo'"
echo ""

echo "CENÁRIO 2: Ambos containers (blue e green) caem"
echo "  - Expectativa: Alertas são ENVIADOS para ambos"
echo "  - Motivo: 'first_failure_since_running' (sibling não está ativo)"
echo ""

cat <<'EOF' > /tmp/test_both_down.json
{
  "receiver": "discord",
  "status": "firing",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "Container Status Alert - app-blue",
        "container": "app-blue",
        "instance": "192.168.1.100:9100",
        "job": "docker-monitor"
      },
      "values": {"A": 0},
      "valueString": "value=0"
    },
    {
      "status": "firing",
      "labels": {
        "alertname": "Container Status Alert - app-green",
        "container": "app-green",
        "instance": "192.168.1.100:9100",
        "job": "docker-monitor"
      },
      "values": {"A": 0},
      "valueString": "value=0"
    }
  ]
}
EOF

echo "Comando para testar:"
echo "curl -X POST http://localhost:5001/webhook/grafana \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d @/tmp/test_both_down.json"
echo ""
echo "Verifique que ambos os alertas são enviados ao Discord"
echo ""

echo "CENÁRIO 3: Container sem padrão blue/green"
echo "  - Expectativa: Comportamento NORMAL (não afetado pela feature)"
echo ""

cat <<'EOF' > /tmp/test_regular_container.json
{
  "receiver": "discord",
  "status": "firing",
  "alerts": [{
    "status": "firing",
    "labels": {
      "alertname": "Container Status Alert - nginx",
      "container": "nginx",
      "instance": "192.168.1.100:9100",
      "job": "docker-monitor"
    },
    "values": {"A": 0},
    "valueString": "value=0"
  }]
}
EOF

echo "Comando para testar:"
echo "curl -X POST http://localhost:5001/webhook/grafana \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d @/tmp/test_regular_container.json"
echo ""
echo "Verifique que o alerta é enviado normalmente"
echo ""

echo "VALIDAÇÃO COM DEBUG_MODE=true:"
echo "  Ative DEBUG_MODE=true no .env para ver logs detalhados:"
echo "    - Detecção do padrão blue/green"
echo "    - Busca do sibling no endpoint"
echo "    - Estado encontrado do sibling"
echo "    - Decisão de supressão"
echo ""

echo "DESABILITAR A FEATURE:"
echo "  Para desabilitar: BLUE_GREEN_SUPPRESSION_ENABLED=false"
echo "  Todos os alertas serão processados normalmente"
echo ""

echo "Arquivos de teste criados em /tmp:"
ls -lh /tmp/test_*.json
