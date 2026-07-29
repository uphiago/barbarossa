# Barbarossa

![Barbarossa, the agent runtime](docs/assets/barbarossa-epic-16x9.png)

Barbarossa is a portable, capability-oriented agent runtime. It connects an
orchestrator to isolated workers through typed tools and durable jobs:

```text
Telegram / API
       |
  Orchestrator
       |
  typed MCP tools
       |
  isolated workers
       |
  durable results
```

The architecture does not require a particular model, provider, worker count,
or concurrency policy. Those are deployment choices. A worker can specialize
in code, local execution, media, networking, or another domain as long as it
implements the capability and job contracts.

This repository contains one reviewed **reference profile** with three
containers:

```text
Hermes (orchestration)
├── Forge
│   ├── runtime
│   └── Codex
└── Recon
    ├── direct network
    └── Tor (explicit)
```

The typed MCP v2 router runs as a hidden subprocess inside the official Hermes
image. It is distributed as an OCI-packaged PEX bundle, not deployed as a
fourth service. Internally, the router uses restricted SSH to reach workers;
Hermes sees typed capabilities rather than an interactive worker shell.

## Core Model

Barbarossa separates four responsibilities:

| Layer | Responsibility |
| --- | --- |
| Orchestrator | Plans, delegates, tracks jobs, and combines results |
| Capability router | Validates typed requests and selects a worker lane |
| Workers | Execute bounded jobs inside domain-specific environments |
| Job store | Retains status, bounded logs, artifacts, and terminal results |

Every execution follows the same lifecycle:

```text
submit -> job_id -> status/logs -> result
                              \-> cancel
```

A capability being advertised means it is available, not that it has been
verified. Controlled audits mark a capability as verified only after a
completed job provides evidence for that exact route.

## Reference Profile

The checked-in profile demonstrates one useful configuration, not an
architectural limit:

| Component | Checked-in configuration |
| --- | --- |
| Hermes main model | DeepSeek V4 Flash through the native API |
| Hermes delegation | Up to three child tasks, one level deep |
| Forge runtime lane | One non-root shell, file, build, and conversion job |
| Forge Codex lane | Codex GPT-5.6 Luna, medium reasoning |
| Codex delegation | Multi-agent enabled, one internal thread per session |
| Recon lane | One authorized network job, direct or explicit Tor |

Forge runtime and Forge Codex can run concurrently. Hermes may also parallelize
independent orchestration across Forge and Recon. DeepSeek and Luna are example
defaults, not implementation requirements. Providers, models, reasoning,
delegation, service resources, and credentials are selected through the
deployment environment without changing source files.

## Configuration

Barbarossa separates deployment settings from Hermes process settings:

| File | Owner | Contents |
| --- | --- | --- |
| `.env` | Barbarossa | Runtime path, image tag, dashboard bind, resources, Codex profile, external credential paths |
| `hermes.env` | Hermes | Main provider/model, delegation, provider credentials, Telegram, Tool Gateway, dashboard authentication |
| `.runtime/compose.env` | Setup/deploy | Generated absolute runtime path and effective immutable image tag |

Both `.env` and `hermes.env` are required and ignored by Git. Only
`.env.example` and `hermes.env.example` are public. The complete
`hermes.env` is injected only into the Hermes service; Forge and Recon receive
explicit allowlisted values from Compose.

The default profile uses:

```dotenv
# hermes.env
HERMES_MODEL_PROVIDER=deepseek
HERMES_MODEL_NAME=deepseek-v4-flash
DEEPSEEK_API_KEY=...
```

Changing providers does not require a code change:

```dotenv
# hermes.env
HERMES_MODEL_PROVIDER=openrouter
HERMES_MODEL_NAME=anthropic/claude-sonnet-4.6
OPENROUTER_API_KEY=...
```

Provider credentials retain their native Hermes names because authentication
can be an API key, OAuth state, a cloud SDK chain, or a custom endpoint.
Hermes OAuth state remains in its private `auth.json`.

When `HERMES_DELEGATION_PROVIDER` and `HERMES_DELEGATION_MODEL` are empty,
child agents inherit the main model. Set them only when delegation should use a
different provider or model.

## Capabilities

| Capability | Reference execution |
| --- | --- |
| `runtime.execute` | Forge runtime lane |
| `media.file.inspect` | Forge runtime lane |
| `code.delegate` | Forge Codex lane |
| `media.image.inspect` | Forge Codex lane |
| `media.image.generate` | Forge Codex lane |
| `media.image.edit` | Forge Codex lane |
| `network.fetch` | Recon with direct HTTP(S) |
| `network.inspect` | Recon with direct authorized tooling |
| `network.tor` | Recon with explicit `torsocks --isolate` |

Codex is a capability inside Forge, not the orchestrator. It can analyze
repositories, implement and review code, run tests, inspect or create images,
and delegate internally when its configured policy permits it.

When configured, the GitHub credential is injected as `GH_TOKEN` only into
Codex and image jobs. It is not exposed to Hermes, Recon, or the Forge runtime
lane.

## Security Boundaries

The reference profile applies the following controls:

- Forge and Recon run as separate non-root users.
- Worker root filesystems are read-only, with bounded tmpfs mounts.
- Every service has CPU, memory, PID, logging, and health limits.
- Workers have no published ports and no Docker socket.
- Forge and Recon do not share a Docker network.
- Workers accept only restricted job RPC, upload, and download SSH commands.
- SSH host checking uses host keys derived from worker-owned key volumes.
- External content and worker results are treated as untrusted input.
- Job logs are bounded and redacted before they return to the orchestrator.
- Tor is selected only by the explicit `network.tor` capability.

The only public host service required in production is SSH. The dashboard
publishes on `127.0.0.1:9119` by default and should be reached locally or
through an SSH tunnel.

## Quick Start

Requirements:

- Docker with Compose
- `uv`
- Python 3
- credentials or OAuth state for the selected Hermes provider
- Telegram bot token
- dashboard credentials
- Codex access token or headless `auth.json`

Clone and prepare the repository:

```bash
git clone https://github.com/uphiago/barbarossa.git
cd barbarossa
cp .env.example .env
cp hermes.env.example hermes.env
```

Configure Docker resources, Codex, and external file paths in `.env`. Configure
the Hermes provider, native provider credentials, Telegram, and dashboard
authentication in `hermes.env`. Keep Codex authentication in the external file configured by
`BARBAROSSA_CODEX_TOKEN_FILE` or `BARBAROSSA_CODEX_AUTH_FILE`.

GitHub access from Codex is optional. Place a scoped credential in the file
configured by `BARBAROSSA_GITHUB_TOKEN_FILE` only when a job needs private
repository access or authenticated GitHub operations. The setup creates an
empty restricted file when no GitHub credential is configured.

Start the reference profile:

```bash
./setup.sh
```

The setup:

1. validates local requirements and required configuration;
2. builds the MCP router PEX and both worker images;
3. generates a fresh restricted worker-control key;
4. derives worker trust from the mounted SSH host-key volumes;
5. starts Forge, Recon, and Hermes in dependency order;
6. runs the complete capability smoke test.

It never disables SSH host checking or copies the private worker-control key
into a worker.

Use the packaged Compose wrapper for later operations so the generated image
tag and runtime directory are always applied:

```bash
scripts/compose.sh ps
scripts/compose.sh logs --since 15m hermes
scripts/compose.sh up -d
```

## Telegram Authorization

Choose one access model before sharing the bot:

- Set `TELEGRAM_ALLOWED_USERS` to a comma-separated static allowlist.
- Leave it empty to use Hermes pairing. An unknown user receives a code but
  cannot use the agent until an operator approves it.

Approve a pairing code from the host running Compose:

```bash
docker compose exec --user hermes hermes \
  /opt/hermes/.venv/bin/hermes pairing approve telegram CODE
```

Review approved and pending identities with:

```bash
docker compose exec --user hermes hermes \
  /opt/hermes/.venv/bin/hermes pairing list
```

Pairing authorization is persistent state. A Telegram session by itself is not
an authorization grant.

## Dashboard

For a local deployment, open:

```text
http://127.0.0.1:9119
```

For a remote deployment, create a local tunnel:

```bash
ssh -NL 9119:127.0.0.1:9119 user@server
```

Then open the same local URL and authenticate with the configured dashboard
credentials. A local SSH alias such as `ovh` can replace `user@server`, but it
is not required by Barbarossa.

## Verification

The smoke test exercises:

- Forge runtime execution;
- Codex delegation and one internal subagent;
- image inspection and generation;
- direct HTTP and explicit Tor;
- non-root worker identities;
- network isolation and absence of Docker sockets;
- secret markers in recent container logs.

Run it on the Docker host:

```bash
cd /path/to/barbarossa
scripts/smoke-remote.sh
```

For a remote host:

```bash
ssh user@server \
  'cd "$HOME/barbarossa" && scripts/smoke-remote.sh'
```

Inbound Telegram images follow a private staged flow:

```text
Telegram attachment
  -> private staging bridge (0600)
  -> orchestrator
  -> media.image.inspect
  -> Forge Codex lane
  -> bounded result
  -> Telegram response
```

The orchestrator does not need an auxiliary vision provider for this route.

## State And Portability

Named volumes retain Hermes jobs, Forge workspaces, Codex home, Recon
workspaces, Tor state, and worker host keys. There is no automatic cleanup or
24-hour retention policy.

This state is operational convenience, not a backup. The deployment is
deliberately disposable: valuable skills, code, and sanitized artifacts should
be promoted manually to a separate private Git repository.

Redeployment generates a new worker-control key and does not migrate legacy
worker state. Review `docker system df` before removing inactive images; image
layers are replaceable deployment material, not backup state.

## Extending Barbarossa

Workers are explicit trust boundaries and are not discovered dynamically.
Adding a worker or capability normally requires:

```text
Compose service and isolated network
  -> worker RPC capability and job implementation
  -> typed MCP router tool and routing policy
  -> orchestrator instruction or skill
  -> capability-specific smoke test
```

Multiple instances can be defined when a deployment needs more capacity,
geographic separation, or different credentials. Each instance still needs an
explicit identity, network boundary, scheduler route, resource policy, and
verification path.

Keep capability interfaces narrow. The orchestrator should submit a typed job,
poll its lifecycle, and retrieve a bounded result instead of receiving a
general-purpose root shell.

## Production

Every pull request runs validation only. Building images and deploying to the
configured host require either a version tag matching `v*` or an explicit
manual workflow dispatch. Ordinary pushes and merges to `main` do not deploy.

Create an annotated release tag from a reviewed `main` commit:

```bash
git switch main
git pull --ff-only
git tag -a v2.0.0 -m "Barbarossa v2.0.0"
git push origin v2.0.0
```

For an intentional deployment without creating a release tag:

```bash
gh workflow run build-deploy.yml --ref main
```

The release workflow:

- tests the router, worker RPC, Hermes configuration, and infrastructure;
- validates Docker Compose;
- publishes immutable SHA-tagged worker images and the router bundle;
- verifies the deployment SSH host key;
- uploads the reviewed source and external runtime credentials;
- performs a direct cutover followed by remote smoke tests.

Deployment secrets and environment-specific evidence remain outside the public
repository. GitHub-native secret scanning, push protection, and repository
rules are repository settings rather than steps in this workflow.

Host hardening lives under [`ops/host`](ops/host), including fail2ban, SSH
forwarding restrictions, and cloud metadata filtering.

## Reference

- [`AGENTS.md`](AGENTS.md): checked-in Hermes operating context
- [`WORKERS.md`](WORKERS.md): capability and lane contract

## License

Barbarossa is distributed under the [MIT License](LICENSE). Use network and
security capabilities only on systems you own or are explicitly authorized to
test.
