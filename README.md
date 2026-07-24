# Barbarossa

Autonomous offensive security agent — three specialized workers, one cluster. Runs on a 4GB VPS.

```
Telegram → hermes → ├─ charlie (collect — recon, scanning, discovery)
                     ├─ oscar   (operate — exploit dev, RE, compilation)
                     └─ papa    (persist — anonymous ops via Tor)
```

## Quick start

```bash
cp .env.example .env     # fill in your API keys + Telegram token
./setup.sh               # builds, configures, starts everything
```

Or manually:

```bash
cp .env.example .env
docker compose up -d --build
```

## Workers

| Worker | Phase | Key tools |
|--------|-------|-----------|
| **charlie** | Collect | nmap, masscan, subfinder, httpx, nuclei, ffuf, naabu, katana, dnsx, amass, python3, curl |
| **oscar** | Operate | Everything in charlie + gdb, gcc, strace, ltrace, xxd, file, jq, socat |
| **papa** | Persist | Tor proxy (SOCKS5 :9050), nmap, python3, curl, torsocks |

## Architecture

Hermes supports multiple LLM providers (DeepSeek, OpenRouter, Anthropic, OpenAI, Ollama). Workers are Docker containers accessed via SSH — single key, no middleware.

## Requirements

- Docker + compose
- LLM API key
- Telegram bot token
- 4GB RAM

## Docs

- [WORKERS.md](WORKERS.md) — agent routing guide (COP model)
- [AGENTS.md](AGENTS.md) — agent context (loaded by Hermes at boot)
