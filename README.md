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

The OVH host runs Ubuntu 26.04 LTS. Its public ingress is limited to key-only
SSH on port 22; the `ubuntu` password and root login are locked. SSH permits
only local forwarding to the loopback-bound Hermes dashboard on port 9119.
UFW denies other inbound and routed traffic, and Fail2ban uses nftables with
one-hour incremental SSH bans capped at 24 hours.

Containers cannot reach the OpenStack metadata endpoints. The persistent
`DOCKER-USER` rule is installed from
`ops/host/barbarossa-container-firewall`, with its systemd unit in the same
directory. SSH and Fail2ban source drop-ins are also under `ops/host/`.

Every service has a memory limit, PID limit, bounded `json-file` logs,
`no-new-privileges`, the Docker default AppArmor and seccomp profiles, and a
healthcheck. `ModemManager`, `udisks2`, and `fwupd-refresh.timer` are disabled
on the virtual server; qemu guest agent, Chrony, automatic security updates,
Docker, SSH, UFW, and Fail2ban remain active.

Host rollback archives contain secrets and stay outside Git:

```text
OVH:   /root/barbarossa-hardening-backup-<timestamp>/
Local: ~/.local/state/barbarossa/backups/<timestamp>/
```

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
