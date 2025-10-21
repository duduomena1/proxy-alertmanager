# Changelog

Todas as mudanças notáveis neste projeto serão documentadas aqui.

O formato é baseado em Keep a Changelog e este projeto segue SemVer.

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
