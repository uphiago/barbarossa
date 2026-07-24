# Worker Cluster — Architecture & Operations

## Topology

```
Telegram → hermes → cluster
              │
              ├── SSH ──→ worker        (recon tools)
              ├── SSH ──→ worker-heavy  (RE + all recon)
              └── SSH ──→ worker-tor    (Tor proxy)
```

## Workers

| Worker | Hostname | Tools |
|--------|----------|-------|
| recon | `worker` | nmap, subfinder, httpx, nuclei, ffuf, naabu, katana, dnsx, amass, masscan, python3, curl |
| heavy | `worker-heavy` | ALL recon + gdb, gcc, strace, ltrace, xxd, file, jq, socat |
| tor | `worker-tor` | nmap, python3, curl, Tor SOCKS5 on :9050 |

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

Single key. Workers resolve by Docker hostname — no hardcoded IPs.

```bash
# From hermes:
ssh -i /opt/data/ssh/key -o StrictHostKeyChecking=no root@worker
ssh -i /opt/data/ssh/key -o StrictHostKeyChecking=no root@worker-heavy
ssh -i /opt/data/ssh/key -o StrictHostKeyChecking=no root@worker-tor

# From host (worker only, via port mapping):
ssh -i ~/.ssh/key -p 2222 root@localhost
```

## Tor usage

```bash
ssh root@worker-tor "torsocks curl -s https://ifconfig.me"
ssh root@worker-tor "torsocks subfinder -d target.com"
curl --socks5-hostname worker-tor:9050 https://target.com
```

⚠️ Tor network may be blocked by some ISPs. If `torsocks` hangs, deploy `worker-tor` on a VPS.

## Starting the cluster

```bash
# Full cluster:
docker compose -f docker-compose.yml -f docker-compose.workers.yml --profile full up -d

# Basic (hermes + recon only):
docker compose up -d
```

## Audit logging

All workers log every SSH command to `/root/output/cmd.log` with timestamps via `ForceCommand`.
