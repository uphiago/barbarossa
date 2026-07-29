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

```mermaid
flowchart TD
    hermes["Hermes<br/>orchestration"]
    forge["Forge<br/>runtime + Codex"]
    recon["Recon<br/>direct network + Tor"]

    hermes -->|execution and code capabilities| forge
    hermes -->|authorized network capabilities| recon
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
| Hermes | DeepSeek V4 Flash through the native API |
| Hermes delegation | Up to three child tasks, one level deep |
| Forge runtime lane | One non-root shell, file, build, and conversion job |
| Forge Codex lane | Codex GPT-5.6 Luna, medium reasoning |
| Codex delegation | Multi-agent enabled, one internal thread per session |
| Recon lane | One authorized network job, direct or explicit Tor |

Forge runtime and Forge Codex can run concurrently. Hermes may also parallelize
independent orchestration across Forge and Recon. Different providers, models,
worker services, and limits can be selected by changing the corresponding
Hermes, Codex, Compose, router, and test configuration.

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
- credentials for the model selected by the checked-in Hermes profile
- Telegram bot token
- dashboard credentials
- Codex access token or headless `auth.json`

Clone and prepare the repository:

```bash
git clone https://github.com/uphiago/barbarossa.git
cd barbarossa
cp .env.example .env
```

For the checked-in profile, add the DeepSeek, Telegram, and dashboard values to
`.env`. Keep Codex authentication in the external file configured by
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

The GitHub Actions workflow:

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
- [`docs/superpowers/specs`](docs/superpowers/specs): architecture rationale
- [`docs/superpowers/plans`](docs/superpowers/plans): reviewed implementation plans

## License

Barbarossa is distributed under the [MIT License](LICENSE). Use network and
security capabilities only on systems you own or are explicitly authorized to
test.
