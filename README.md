# Barbarossa

**COP — three-phase agent cluster.** CHARLIE collects, OSCAR operates, PAPA persists.

```
Telegram → hermes → ├─ charlie (collect: subfinder, nuclei, nmap, ffuf...)
                     ├─ oscar   (operate: gdb, gcc, exploit dev, RE...)
                     └─ papa    (persist: Tor, lateral movement, stealth...)
```

## Quick start

```bash
cp .env.example .env   # configure API keys + Telegram token
docker compose up -d   # sobe todos os workers + hermes
```

## Workers

| Worker | Phase | Tools |
|--------|-------|-------|
| **charlie** | Collect | nmap, subfinder, httpx, nuclei, ffuf, naabu, katana, dnsx, amass, masscan, python3 |
| **oscar** | Operate | ALL above + gdb, gcc, strace, ltrace, xxd, file, jq, socat |
| **papa** | Persist | nmap, python3, curl, subfinder, Tor SOCKS5 on :9050 |

## Architecture

Hermes gerencia múltiplos provedores LLM (DeepSeek, OpenRouter, Anthropic, OpenAI, Ollama...). Workers são containers Docker acessados via SSH — chave única, sem middleware, terminal puro. Roda em VPS de 4GB.

## Docs

- [WORKERS.md](WORKERS.md) — guia de roteamento pro agent (COP model)
