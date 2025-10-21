"""Pacote webapp modular para o proxy do Alertmanager/Grafana -> Discord.

Este pacote contém:
- constants: variáveis de ambiente e mapas de configuração
- utils: utilitários de formatação e helpers
- enrichment: funções de extração/enriquecimento de dados
- detection: detecção de tipo/severidade
- formatters: validação e formatação de mensagens
- services: integração com serviços externos (Discord)
- controller: criação do Flask app e endpoints
"""
