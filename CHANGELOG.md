# Changelog

Todas as mudanças notáveis neste projeto serão documentadas aqui.

O formato é baseado em Keep a Changelog e este projeto segue SemVer.

## [1.2.0] - 2025-11-24

### Added

- **Supressão inteligente para deployments Blue/Green**:
  - Detecta automaticamente pares de containers com nomenclatura `app-blue`/`app-green` ou `app_blue`/`app_green` (case-insensitive).
  - Suprime alertas quando um container cai mas seu par está rodando no mesmo endpoint Portainer.
  - Se ambos os containers do par caem, os alertas são enviados normalmente.
  - Novas funções: `extract_blue_green_base()` e `find_active_sibling()` em `app/suppression.py`.
- Nova variável de ambiente:
  - `BLUE_GREEN_SUPPRESSION_ENABLED` (default: true) — permite desabilitar a feature.
- Logging detalhado (DEBUG) das decisões de supressão blue/green.
- Testes automatizados para blue/green:
  - Detecção de nomenclatura (hífen, underscore, case-insensitive).
  - Supressão quando sibling está ativo.
  - Alertas quando ambos caem.
  - Comportamento com feature desabilitada.
- Script de teste manual: `test/test_blue_green_manual.sh`.

### Changed

- `ContainerSuppressor.should_send()` agora aceita parâmetros `portainer_client` e `endpoint_id` para verificação blue/green.
- Chamadas de supressão em `app/controller.py` e `app/portainer_monitor.py` atualizadas para passar cliente Portainer.
- `docs/ENV_VARS.md` atualizado com documentação da feature blue/green.

### Requirements

- Requer `CONTAINER_VALIDATE_WITH_PORTAINER=true` para funcionar corretamente.
- O par blue/green deve estar no mesmo endpoint Portainer.

## [1.1.0] - 2025-10-21

### Added

- Supressão de alertas de container por estado (state machine):
  - Envia apenas o primeiro alerta de queda (down/restarting/exited/...) e bloqueia reenvios até o container voltar a `running`.
  - Allowlist para containers `paused` intencionais (não alerta e não ativa supressão).
- Integração da supressão em dois fluxos:
  - Endpoint principal `/alert` (alertas do Grafana) — usa Portainer quando habilitado, com fallback para heurística do payload.
  - Monitor ativo do Portainer (PortainerMonitor) — detecta quedas diretamente e respeita a supressão por estado.
- Novas variáveis de ambiente:
  - `CONTAINER_SUPPRESS_REPEATS` (default: true)
  - `CONTAINER_SUPPRESS_TTL_SECONDS` (default: 86400)
  - `CONTAINER_PAUSED_ALLOWLIST` (lista separada por vírgula)
- Documentação expandida:
  - `docs/ENV_VARS.md` — referência completa de variáveis.
  - `docs/CONTAINER_SUPPRESSION.md` — guia da supressão por estado com exemplos.
  - `docs/PORTAINER_INTEGRATION.md` — guia da integração e monitor ativo.
- Testes automáticos básicos para a supressão: `test/test_suppression.py`.

### Changed

- `README.md` atualizado com menu de navegação, exemplos de configuração para supressão e Portainer, e links para a documentação.
- `.env.example` atualizado com as novas variáveis de supressão.

### Fixed

- Pequenas correções de formatação Markdown e headings.

### Migration Notes

- A supressão por estado vem habilitada por padrão (`CONTAINER_SUPPRESS_REPEATS=true`).
- Se preferir o comportamento antigo (apenas dedupe por TTL), defina `CONTAINER_SUPPRESS_REPEATS=false`.
- Para containers que podem ficar `paused` por longos períodos sem alertar, use `CONTAINER_PAUSED_ALLOWLIST`.

[1.1.0]: https://github.com/duduomena1/proxy-alertmanager/releases/tag/v1.1.0
