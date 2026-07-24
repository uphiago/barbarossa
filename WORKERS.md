# Multi-Worker Cluster — Architecture & Operations

## Topology

```
Telegram ──→ hermes (agentiko-hermes) ──SSH──→ cluster
                   │                              │
                   │ /opt/data/skills/            ├── worker (recon, Alpine)
                   │ /opt/data/AGENTS.md          ├── worker-heavy (RE, Debian)
                   │ /opt/data/ssh/               └── worker-tor (Tor, Alpine)
                   │ agentiko_key
                   │
                   │ Hermes agent uses DeepSeek
                   │ Loads 171 skills from GitHub
                   │ Connects to workers via SSH
```

## Workers

| Worker | Hostname | Image | Size | Tools |
|--------|----------|-------|------|-------|
| recon | `worker` (172.20.0.4) | agentiko-worker:latest | 1.27GB | nmap, subfinder, httpx, nuclei, ffuf, naabu, katana, dnsx, amass, masscan, python3, curl |
| heavy | `agentiko-worker-heavy` (172.20.0.3) | agentiko-worker-heavy:latest | 1.6GB | ALL recon tools + gdb, gcc, strace, ltrace, xxd, file, jq, socat |
| tor | `agentiko-worker-tor` (172.20.0.5) | agentiko-worker-tor:latest | 218MB | nmap, python3, curl, Tor SOCKS5 :9050 |

## When to use each worker

| Task | Worker |
|------|--------|
| subfinder, httpx, nuclei, ffuf, naabu, katana, amass, masscan | **worker** |
| nmap, curl, Python scripts, general recon | **worker** |
| gdb, strace, ltrace, xxd — debug/RE | **worker-heavy** |
| gcc, make — compile exploits | **worker-heavy** |
| Binary analysis, ELF parsing | **worker-heavy** |
| Anonymous scanning via Tor | **worker-tor** |
| Bypassing rate limits / geo-blocks | **worker-tor** |

## SSH

Single key for all workers: `/opt/data/ssh/agentiko_key`

```bash
# From hermes:
ssh -i /opt/data/ssh/agentiko_key -o StrictHostKeyChecking=no root@worker
ssh -i /opt/data/ssh/agentiko_key -o StrictHostKeyChecking=no root@agentiko-worker-heavy
ssh -i /opt/data/ssh/agentiko_key -o StrictHostKeyChecking=no root@agentiko-worker-tor

# From host:
ssh -i ~/.ssh/agentiko_key -p 2222 root@localhost  # worker only
```

## Tor usage

```bash
# Wrap any command with torsocks:
ssh root@agentiko-worker-tor "torsocks curl -s https://ifconfig.me"
ssh root@agentiko-worker-tor "torsocks subfinder -d target.com"

# Or use SOCKS5 proxy directly:
curl --socks5-hostname agentiko-worker-tor:9050 https://target.com
```

**⚠️ Tor network may be blocked by some ISPs or Docker configurations. If `torsocks` hangs indefinitely, the Tor network is unreachable from that host. Deploy worker-tor on a VPS for full functionality.**

## Starting the cluster

```bash
cd ~/repositories/homelab/agentiko

# Full cluster (hermes + all 3 workers):
docker compose -f docker-compose.yml -f docker-compose.workers.yml --profile full up -d

# Basic (hermes + recon worker only):
docker compose up -d

# Status:
docker compose -f docker-compose.yml -f docker-compose.workers.yml --profile full ps
```

## Audit logging

All workers have `ForceCommand=/usr/local/bin/sshd-shell` which logs every SSH command to `/root/output/cmd.log` with timestamps.

## Image build

```bash
# Rebuild specific worker:
docker compose -f docker-compose.yml -f docker-compose.workers.yml --profile full build worker-heavy

# Rebuild all:
docker compose -f docker-compose.yml -f docker-compose.workers.yml --profile full build
```
