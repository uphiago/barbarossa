# Barbarossa — OpenCode lane (free DeepSeek) with multi-agent orchestration

> Agent record: what was implemented, the contracts exposed to Hermes, and how to
> validate, apply and revert this release.

**Status:** implemented and validated locally on 2026-10-16; shipped to
production from `main` through the `build-deploy.yml` workflow (manual dispatch),
with automatic rollback on deploy.

## Goal

Add a multi-agent engineering lane in Forge using the OpenCode CLI and the free
`opencode/deepseek-v4.1-flash-free` model, keeping the Codex lane separate as a
fallback. The Hermes main model does not change.

## Why OpenCode runs inside Forge

The OpenCode free tier only works "from within OpenCode": the external API
answers `403 FreeTierError` for direct use (verified on 2026-10-16). With the
CLI inside the Forge job, usage is legitimate, anonymous and requires no new
credential.

## Contracts (what agents use)

| Item | Value |
| --- | --- |
| Capability | `code.opencode` |
| MCP tool | `code_opencode(prompt, input_paths?, timeout_seconds?=2700, opencode_variant?)` |
| Worker / lane | `forge` / `opencode` (one job at a time per lane) |
| Model | `opencode/deepseek-v4.1-flash-free` (`BARBAROSSA_OPENCODE_MODEL`) |
| Variants | `low` · `high` (default) · `max` — `opencode_variant` / `BARBAROSSA_OPENCODE_VARIANT` |
| Internal roles | `orchestrator` (primary) + `explorer` (#low) · `implementer` (#high) · `tester` (#high) · `reviewer` (#max) |
| Parallelism | up to 10 subagents in parallel; subagents spawn no grandchildren |
| Combined artifact | `outputs/final.md` (read only through `job_result`) |
| Secrets | None new; `GH_TOKEN` enters the job as in the other code lanes |

## Changes per file

- Router: `models.py` (capability, lane, 2700s policy, `opencode_variant`),
  `store.py` (`job_opencode_` prefix), `scheduler.py` (4 lanes), `server.py`
  (`code_opencode` tool), `cli.py` (`--opencode-variant`).
- Worker: `containers/shared/worker-rpc.py` (lane map, job id regex,
  `opencode_command()` → `opencode run --standalone --auto --agent orchestrator
  --model <model>#<variant>`, per-job staging of the config and of
  `XDG_DATA_HOME`/`XDG_STATE_HOME` inside the scratch, supervisor allowlist).
- Image: `containers/forge/Dockerfile` (`@opencode/cli@2.0.31` with
  `--allow-scripts=@opencode/cli`, pruning of unused binaries, an
  `opencode --version` guard, `config/opencode` COPY),
  `containers/forge/forge-entrypoint.sh` (validates and propagates
  `BARBAROSSA_OPENCODE_MODEL`/`_VARIANT`).
- New config: `config/opencode/opencode.jsonc` + `config/opencode/agents/*.md`.
- Compose: env vars with defaults, bind-ro `./config/opencode`, skill mount.
- Docs/skills: `AGENTS.md`, `README.md`, `WORKERS.md`,
  `skills/hermes/barbarossa-routing/SKILL.md`,
  `skills/hermes/barbarossa-opencode/SKILL.md`.
- Tests: the router suites, `tests/test-worker-rpc.py`,
  `tests/container-integration.sh` (`opencode --version` + config in the image),
  `tests/infra-regression.sh`, `scripts/smoke-remote.sh` (2 new checks).

## Local evidence (2026-10-16)

- `opencode run` with a clean HOME (no account/auth): OK; non-git directory: OK;
  `low`/`high`/`max` variants: OK.
- Orchestrator + 3 subagents in parallel (child sessions) with consolidation: OK.
- `@opencode/cli@2.0.31` under npm 12.2.0 with `--allow-scripts=@opencode/cli`:
  installs, the post-install script runs, `opencode --version` = `2.0.31`;
  pruning of unused binaries took the install from 809 MB to 202 MB.
- Production host: x86_64 with avx2; enough disk space for the new release with
  the rollback retained.

## Apply and revert

- Apply: push to `main` + `gh workflow run build-deploy.yml --ref main`. The
  pipeline runs the tests, builds/publishes the images, cuts over on the host and
  runs `scripts/smoke-remote.sh` (including the `code.opencode` checks).
- Revert: a cutover/smoke failure restores the previous release automatically;
  the rollback release stays retained on the host.
- Manual operation (without Hermes): `router submit --capability code.opencode
  --prompt '...' --opencode-variant max --wait`.

## Risks and follow-ups

- The free tier is temporary and has no documented rate-limit SLA; parallelism is
  bounded by prompt policy + the agents' `steps`.
- Forge memory (1408m) is shared between runtime/Codex/OpenCode; under
  simultaneous load, raise `BARBAROSSA_FORGE_MEMORY` in `.env`.
- If the free tier goes away, the deploy smoke check fails and reverts: treat it
  as provider unavailability, not as a Barbarossa regression.
