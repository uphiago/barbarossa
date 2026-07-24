# Barbarossa

**Three-phase agent cluster for autonomous operations.** CHARLIE collects, OSCAR operates, PAPA persists.

```
Telegram → hermes → ├─ charlie (collect: subfinder, nuclei, nmap, ffuf...)
                     ├─ oscar   (operate: gdb, gcc, exploit dev, RE...)
                     └─ papa    (persist: Tor, lateral movement, stealth...)
```

## Quick start

```bash
cp .env.example .env   # add your API keys
./setup.sh             # builds, configures, starts everything
```

## Workers — COP Model

| Worker | Phase | Tools |
|--------|-------|-------|
| **charlie** | Collect | nmap, subfinder, httpx, nuclei, ffuf, naabu, katana, dnsx, amass, masscan, python3 |
| **oscar** | Operate | ALL above + gdb, gcc, strace, ltrace, xxd, file, jq, socat |
| **papa** | Persist | nmap, python3, curl, subfinder, Tor SOCKS5 :9050 |

## Architecture

Hermes manages multiple LLM providers (DeepSeek, OpenRouter, Anthropic, OpenAI, Ollama...). Workers are specialized Docker containers accessed via SSH. Single key, zero middleware, pure terminal.

## Requirements

- Docker + compose
- LLM provider API key
- Telegram bot token
- 4GB RAM (charlie + hermes) | 8GB RAM (cluster completo)
- Hermes usa imagem pre-built do Docker Hub (~1GB pull)

## Docs

- [WORKERS.md](WORKERS.md) — agent routing guide and COP model
