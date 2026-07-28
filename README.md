# Barbarossa

Autonomous offensive security agent — three specialized workers, one cluster. Runs on a 4GB VPS.

```
Telegram → hermes → ├─ charlie (collect — recon, scanning, discovery)
                     ├─ oscar   (operate — exploit dev, RE, compilation)
                     └─ papa    (persist — anonymous ops via Tor)
```

## Quick start

Local development:

```bash
cp .env.example .env
# Fill API, Telegram, model, and dashboard values.
./setup.sh
```

`setup.sh` is local-only. It generates a development SSH key outside Git,
publishes its public key under the ignored `worker/` runtime directory, builds
the images, and configures Hermes.

Production is deployed by `.github/workflows/build-deploy.yml`. On the first
deployment, the workflow reuses the active Hermes key when available or
generates one under `~/.config/barbarossa` on the OVH host. The optional
`BARBAROSSA_WORKER_SSH_KEY_B64` GitHub secret can supply a replacement key for
a later, manually dispatched rotation. Key material remains outside the clone.

## Workers

| Worker | Phase | Key tools |
|--------|-------|-----------|
| **charlie** | Collect | nmap, masscan, subfinder, httpx, nuclei, ffuf, naabu, katana, dnsx, amass, python3, curl |
| **oscar** | Operate | Everything in charlie + gdb, gcc, strace, ltrace, xxd, file, jq, socat |
| **papa** | Persist | Tor proxy (SOCKS5 :9050), nmap, Python, curl |

## Architecture

Hermes supports multiple LLM providers (DeepSeek, OpenRouter, Anthropic, OpenAI, Ollama). Workers are Docker containers accessed via SSH — single key, no middleware.

## Production hardening

Reusable host controls live under `ops/host/`. The public repository
intentionally omits live addresses, account state, backup locations, completed
deployment evidence, and other environment-specific operational records.

Every service has bounded resources and logs, healthchecks, and basic container
containment. Production secrets and rollback material stay outside Git.

Papa provides Tor but does not enforce Tor-only egress. Commands requiring
anonymity must still explicitly use `--socks5-hostname` or `torsocks`.

## Requirements

- Docker + compose
- LLM API key
- Telegram bot token
- Dashboard username, password, and signing secret
- 4GB RAM

## Tor

From Papa, make curl resolve the target through Tor:

```bash
curl --socks5-hostname 127.0.0.1:9050 \
  https://check.torproject.org/api/ip
```

A healthy response contains `"IsTor":true`.

## Docs

- [WORKERS.md](WORKERS.md) — agent routing guide (COP model)
- [AGENTS.md](AGENTS.md) — agent context (loaded by Hermes at boot)
- [ops/host](ops/host) — reproducible OVH host hardening files
