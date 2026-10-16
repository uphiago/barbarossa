# Barbarossa — Lane OpenCode (DeepSeek free) com orquestração multi-agente

> Registro para agentes: descreve o que foi implementado, os contratos expostos
> ao Hermes e como validar, aplicar e reverter esta release.

**Status:** em produção desde 2026-10-16 (release `65b9af02`; smoke completo
com `verified code.opencode` ×2, incluindo o subagente `explorer`).

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

### Permissões e isolamento (verificado empiricamente, v2.0.31)

- As regras `permissions` no frontmatter dos agentes agem sobre **nomes de
  tool** do OpenCode v2: `edit` (remove `write`+`edit`), `shell`, `subagent`
  etc. O vocabulário dos docs v1 (`bash`, `task`) é **inerte** aqui — validado
  por A/B com agentes-sonda em 2026-10-16.
- Mapa efetivo: `orchestrator` (`subagent` allow); `explorer` e `tester`
  (deny `edit` + `subagent`); `implementer` (deny `subagent`); `reviewer`
  (deny `edit` + `shell` + `subagent` — somente leitura efetivo).
- `share: "disabled"` no `opencode.jsonc`: sessões nunca são compartilháveis.
  Estado de sessão vive no scratch do job (`XDG_DATA_HOME`/`XDG_STATE_HOME`),
  nada no home persistente; `username` (identidade de telemetria) não é
  definido. Não há kill-switch global de telemetria documentado.
- Catálogo free observado em 2026-10-16 (`opencode models`): o DeepSeek em uso
  mais `glm-5.3-flash-free`, `nemotron-3-ultra-free`,
  `nemotron-3.5-lightning-free`, `nemotron-3.5-super-vl-free`,
  `mimo-v2.6-flash-free`, `longcat-2.5-preview-free`, `beam-free`,
  `ll-alpha-free`, `muse-spark-1.3-contributor-free`, `space-bunny-free`.
  Trocar de modelo é decisão de deploy (`BARBAROSSA_OPENCODE_MODEL`), não de
  job.

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
- Config nova: `config/opencode/opencode.jsonc` (`share: disabled`, `update:
  disable`, `snapshots: false`) + `config/opencode/agents/*.md`.
- Scripts: `scripts/deploy-runtime-files.sh` (preflight de espaço ≥4 GiB antes
  do pull), `scripts/prune-rollback-images.sh` (coleta operacional de rollbacks
  antigos; ver `docs/2026-10-16-deploy-disk-incident.md`).
- Compose: env vars com defaults, bind-ro `./config/opencode`, mount da skill.
- Docs/skills: `AGENTS.md`, `README.md`, `WORKERS.md`,
  `skills/hermes/barbarossa-routing/SKILL.md`,
  `skills/hermes/barbarossa-opencode/SKILL.md`.
- Testes: suites do router, `tests/test-worker-rpc.py`,
  `tests/container-integration.sh` (`opencode --version` + config na imagem),
  `tests/infra-regression.sh` (asserts de config/permissões + drill do helper
  de prune com docker mockado), `scripts/smoke-remote.sh` (2 checagens novas).

## Evidência local (2026-10-16)

- `opencode run` com HOME limpo (sem conta/auth): OK; diretório não-git: OK;
  variantes `low`/`high`/`max`: OK.
- Orquestrador + 3 subagentes em paralelo (child sessions) com consolidação: OK.
- `@opencode/cli@2.0.31` sob npm 12.2.0 com `--allow-scripts=@opencode/cli`:
  instala, pós-instalação executa, `opencode --version` = `2.0.31`; poda dos
  binários não usados levou o install de 809 MB para 202 MB.
- Permissões confirmadas por sonda: `edit`/`shell`/`subagent` removem os tools
  correspondentes; drill do helper de prune (docker mockado) cobre lock,
  dry-run e apply sem tocar a release retida nem imagens de terceiros.

## Evidência em produção (2026-10-16)

- Host x86_64 com avx2. Deploy `65b9af02` verde; smoke no host:
  `verified runtime.execute`, `verified code.delegate` ×2, `verified
  code.opencode` ×2 (o segundo lança o subagente `explorer`),
  `media.image.inspect`/`generate` e checagens de rede.
- Rollback retido: `~/.config/barbarossa/runtime/rollback/release.YVc6iCSS`.
- Credencial Codex estável após o smoke (mesmo hash no volume, no host e no
  secret) — ver `docs/2026-10-16-codex-auth-persistence.md`.
- O primeiro deploy (`a379e01`) caiu por credencial Codex expirada (não pela
  lane) e o rollback automático atuou como projetado.

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
- Disco do host: cada release retém ≈3 GiB de rollback; o deploy agora falha
  cedo com menos de 4 GiB livres — usar
  `scripts/prune-rollback-images.sh --apply` quando o preflight acusar
  (ver `docs/2026-10-16-deploy-disk-incident.md`).
- Se o free tier sair do ar, o smoke do deploy falha e reverte: tratar como
  indisponibilidade do provedor, não como regressão do Barbarossa.
- Follow-up: login Codex dedicado do cluster (`CODEX_HOME` separado) para não
  compartilhar a cadeia de refresh com o workstation.
