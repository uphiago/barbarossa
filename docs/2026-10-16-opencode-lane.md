# Barbarossa — Lane OpenCode (DeepSeek free) com orquestração multi-agente

> Registro para agentes: descreve o que foi implementado, os contratos expostos
> ao Hermes e como validar, aplicar e reverter esta release.

**Status:** implementado e validado localmente em 2026-10-16; aplicação em
produção pela `main` via workflow `build-deploy.yml` (dispatch manual), com
rollback automático no deploy.

## Objetivo

Adicionar uma lane de engenharia multi-agente no Forge com o OpenCode CLI e o
modelo gratuito `opencode/deepseek-v4.1-flash-free`, mantendo a lane Codex
separada como fallback. O modelo principal do Hermes não muda.

## Por que o OpenCode roda dentro do Forge

O free tier do OpenCode só funciona "from within OpenCode": a API externa
responde `403 FreeTierError` para uso direto (verificado em 2026-10-16). Com o
CLI dentro do job do Forge, o uso é legítimo, anônimo e sem credencial nova.

## Contratos (o que os agentes usam)

| Item | Valor |
| --- | --- |
| Capability | `code.opencode` |
| Tool MCP | `code_opencode(prompt, input_paths?, timeout_seconds?=2700, opencode_variant?)` |
| Worker / lane | `forge` / `opencode` (um job por vez por lane) |
| Modelo | `opencode/deepseek-v4.1-flash-free` (`BARBAROSSA_OPENCODE_MODEL`) |
| Variantes | `low` · `high` (default) · `max` — `opencode_variant` / `BARBAROSSA_OPENCODE_VARIANT` |
| Papéis internos | `orchestrator` (primário) + `explorer` (#low) · `implementer` (#high) · `tester` (#high) · `reviewer` (#max) |
| Paralelismo | até 10 subagentes em paralelo; subagentes não lançam netos |
| Artefato combinado | `outputs/final.md` (ler somente via `job_result`) |
| Segredos | Nenhum novo; `GH_TOKEN` entra no job como nas demais lanes de código |

## Mudanças por arquivo

- Router: `models.py` (capability, lane, política 2700s, `opencode_variant`),
  `store.py` (prefixo `job_opencode_`), `scheduler.py` (4 lanes),
  `server.py` (tool `code_opencode`), `cli.py` (`--opencode-variant`).
- Worker: `containers/shared/worker-rpc.py` (lane map, regex de job id,
  `opencode_command()` → `opencode run --standalone --auto --agent orchestrator
  --model <model>#<variant>`, staging por job do config e de
  `XDG_DATA_HOME`/`XDG_STATE_HOME` no scratch, allowlist do supervisor).
- Image: `containers/forge/Dockerfile` (`@opencode/cli@2.0.31` com
  `--allow-scripts=@opencode/cli`, poda dos binários não usados, guarda
  `opencode --version`, COPY de `config/opencode`),
  `containers/forge/forge-entrypoint.sh` (valida e propaga
  `BARBAROSSA_OPENCODE_MODEL`/`_VARIANT`).
- Config nova: `config/opencode/opencode.jsonc` + `config/opencode/agents/*.md`.
- Compose: env vars com defaults, bind-ro `./config/opencode`, mount da skill.
- Docs/skills: `AGENTS.md`, `README.md`, `WORKERS.md`,
  `skills/hermes/barbarossa-routing/SKILL.md`,
  `skills/hermes/barbarossa-opencode/SKILL.md`.
- Testes: suites do router, `tests/test-worker-rpc.py`,
  `tests/container-integration.sh` (`opencode --version` + config na imagem),
  `tests/infra-regression.sh`, `scripts/smoke-remote.sh` (2 checagens novas).

## Evidência local (2026-10-16)

- `opencode run` com HOME limpo (sem conta/auth): OK; diretório não-git: OK;
  variantes `low`/`high`/`max`: OK.
- Orquestrador + 3 subagentes em paralelo (child sessions) com consolidação: OK.
- `@opencode/cli@2.0.31` sob npm 12.2.0 com `--allow-scripts=@opencode/cli`:
  instala, pós-instalação executa, `opencode --version` = `2.0.31`; poda dos
  binários não usados levou o install de 809 MB para 202 MB.
- Host de produção: x86_64 com avx2; espaço em disco suficiente para a release
  nova com rollback retido.

## Aplicar e reverter

- Aplicar: push na `main` + `gh workflow run build-deploy.yml --ref main`.
  O pipeline roda testes, constrói/publica as imagens, faz o cutover no host e
  executa `scripts/smoke-remote.sh` (incluindo as checagens `code.opencode`).
- Reverter: falha de cutover/smoke restaura a release anterior
  automaticamente; a release de rollback fica retida no host.
- Operação manual (sem Hermes): `router submit --capability code.opencode
  --prompt '...' --opencode-variant max --wait`.

## Riscos e follow-ups

- Free tier é temporário e sem SLA documentado de rate limit; o paralelismo é
  limitado por política de prompt + `steps` dos agentes.
- Memória do Forge (1408m) é compartilhada entre runtime/Codex/OpenCode; sob
  carga simultânea, subir `BARBAROSSA_FORGE_MEMORY` no `.env`.
- Se o free tier sair do ar, o smoke do deploy falha e reverte: tratar como
  indisponibilidade do provedor, não como regressão do Barbarossa.
