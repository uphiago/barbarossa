# Barbarossa

Barbarossa is a portable three-container agent runtime:

```text
Telegram / API
       |
     Hermes
     /    \
  Forge   Recon
```

- **Hermes** plans and routes with DeepSeek V4 Flash. It can run up to three
  child tasks in parallel. DeepSeek runs through its native API endpoint.
- **Forge** provides one general runtime lane and one Codex lane. The lanes can
  run concurrently.
- **Recon** provides one isolated lane for authorized network work, using
  direct egress by default and Tor only when explicitly requested.

The typed MCP v2 router runs as a hidden subprocess inside the official Hermes
image. It is packaged as an OCI artifact, but it is not a fourth service.
Forge and Recon have no shared network, published port, Docker socket, or root
login.

The only public host service required by Barbarossa is SSH. The Hermes
dashboard binds to `127.0.0.1:9119` and is reached through the `ssh ovh` local
forward, not through a public Docker port.

## Capabilities

| Capability | Execution |
| --- | --- |
| Shell, files, builds, conversions | Forge runtime lane |
| Repository engineering | Codex GPT-5.6 Luna, medium reasoning |
| Image inspection, generation, editing | Codex lane |
| HTTP and authorized network tools | Recon, direct |
| Explicit anonymous network work | Recon, Tor |

Codex is the engineering capability inside Forge and may create one internal
subagent. Hermes can independently parallelize orchestration across Forge and
Recon.

## Local Setup

Requirements:

- Docker with Compose
- `uv`
- Python 3
- DeepSeek API key
- Telegram bot token
- Dashboard credentials
- Codex access token or headless `auth.json`

```bash
cp .env.example .env
# Fill the provider, Telegram, dashboard, and external file values.
./setup.sh
```

The setup builds the PEX and both worker images, generates a fresh restricted
worker key, derives worker host trust from the mounted host-key volumes, starts
the three services, and runs capability smoke tests. It never disables SSH
host checking or copies a private worker key into a worker.

## Verification

The remote smoke test exercises runtime execution, Codex delegation and
subagents, image inspection and generation, direct HTTP, explicit Tor, worker
UIDs, network isolation, and secret-free logs:

```bash
ssh ovh 'cd "$HOME/barbarossa" && scripts/smoke-remote.sh'
```

Inbound image attachments are copied atomically from the private Hermes cache
to `/opt/data/barbarossa-transfer` with mode `0600`. The gateway then instructs
Hermes to inspect each staged path with `media_image_inspect`; it does not call
an auxiliary vision provider. The expected flow is:

```text
Telegram attachment
  -> private staging bridge
  -> Hermes (DeepSeek)
  -> hidden MCP media_image_inspect
  -> Forge codex lane
  -> Codex vision
  -> outputs/final.txt
  -> Hermes response
```

The dashboard is available locally while the SSH session is active:

```bash
ssh ovh
# Open http://127.0.0.1:9119
```

## State Model

Named volumes retain Hermes jobs, Forge workspaces, Codex home, Recon
workspaces, Tor state, and worker host keys. There is no automatic cleanup or
24-hour retention policy. This state is operational convenience, not a backup.

The deployment is deliberately disposable. Valuable skills, code, and
sanitized artifacts should be promoted manually to a separate private Git
repository. Redeployment generates a new worker-control key and does not
migrate legacy worker state.

## Production

The GitHub Actions workflow tests the router and containers, scans Git history
for secrets, publishes immutable SHA-tagged images, verifies the OVH SSH host
key, and performs a direct cutover followed by remote smoke tests. Deployment
secrets and environment-specific evidence remain outside this public
repository.

Host hardening remains under [`ops/host`](ops/host), including fail2ban, SSH
forwarding restrictions, and cloud metadata filtering.

## Reference

- [`AGENTS.md`](AGENTS.md): Hermes operating context
- [`WORKERS.md`](WORKERS.md): capability and lane contract
- [`docs/superpowers/specs`](docs/superpowers/specs): architecture rationale

## License

Barbarossa is distributed under the [MIT License](LICENSE). Use network and
security capabilities only on systems you own or are explicitly authorized to
test.
