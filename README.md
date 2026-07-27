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

Production is deployed by `.github/workflows/build-deploy.yml`. The workflow
requires the base64-encoded private worker key in the
`BARBAROSSA_WORKER_SSH_KEY_B64` GitHub secret. It derives the public key on the
OVH host and keeps all key material outside the clone.

## Workers

| Worker | Phase | Key tools |
|--------|-------|-----------|
| **charlie** | Collect | nmap, masscan, subfinder, httpx, nuclei, ffuf, naabu, katana, dnsx, amass, python3, curl |
| **oscar** | Operate | Everything in charlie + gdb, gcc, strace, ltrace, xxd, file, jq, socat |
| **papa** | Persist | Tor proxy (SOCKS5 :9050), nmap, Python, curl |

## Architecture

Hermes supports multiple LLM providers (DeepSeek, OpenRouter, Anthropic, OpenAI, Ollama). Workers are Docker containers accessed via SSH — single key, no middleware.

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
