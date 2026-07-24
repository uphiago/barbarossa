# Barbarossa

**Multi-worker agent cluster for autonomous offensive security operations.**

A two-container design (agent + workers) where the agent thinks and workers execute — each with its own toolset and network profile.

```
Telegram → barbarossa-hermes → ├─ worker (recon: nmap, subfinder, nuclei, ffuf...)
                                ├─ worker-heavy (RE: gdb, gcc, strace...)
                                └─ worker-tor (anon: Tor SOCKS5)
```

## Quick start

```bash
cp .env.example .env   # add your API keys
./setup.sh             # builds, configures, starts everything
```

## Workers

| Worker | Size | Tools |
|--------|------|-------|
| **worker** | 1.27GB | nmap, subfinder, httpx, nuclei, ffuf, naabu, katana, dnsx, amass, masscan, python3 |
| **worker-heavy** | 1.6GB | ALL recon tools + gdb, gcc, strace, ltrace, xxd, file |
| **worker-tor** | 218MB | nmap, python3, Tor SOCKS5 :9050 |

## Skills

171 offensive security skills from [recon-skills](https://github.com/uphiago/recon-skills) — auto-synced from GitHub on every boot.

## Architecture

Agent runs on DeepSeek. Workers are specialized Docker containers accessed via SSH. Single key, zero middleware, pure terminal.

## Requirements

- Docker + compose
- DeepSeek API key
- Telegram bot token
- 8GB RAM (full cluster), 4GB (recon only)

## Docs

- [WORKERS.md](WORKERS.md) — cluster operations and routing
- [recon-skills](https://github.com/uphiago/recon-skills) — skill catalog
