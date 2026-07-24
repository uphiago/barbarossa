# COP — Three-Phase Worker Model

**CHARLIE, OSCAR, PAPA.** Each maps to a phase of an operation. Not "different tool installs" — different objectives.

## Decision Matrix

| Phase | Worker | Objective | Tools |
|-------|--------|-----------|-------|
| **Collect** | `charlie` | Discover attack surface | subfinder, httpx, nuclei, ffuf, nmap, naabu, katana, dnsx, amass, masscan, python3, curl |
| **Operate** | `oscar` | Exploit, analyze, build | ALL of charlie + gdb, gcc, strace, ltrace, xxd, file, socat, jq, binutils |
| **Persist** | `papa` | Move laterally, stay hidden | nmap, python3, curl, subfinder, Tor SOCKS5 :9050 |

## Flow

```
charlie → map the surface → 15 subdomains, 12 live, 3 with vulns
oscar   → exploit the vulns → compile PoC, launch, get shell
papa    → pivot from shell  → lateral movement, credential dump, exfil
charlie → re-scan from inside → new surface, repeat
```

The loop: charlie doesn't stop after phase 1. After papa opens a door, charlie rescans from the new perspective.

## Workers

### charlie (collect)
Fast. Disposable. Throw away and rebuild anytime. Volume persists scan output.

### oscar (operate)
Stateful. Keep compiled exploits, analysis artifacts, reverse engineering notes here. Don't treat as disposable.

### papa (persist)
Anonymous. All outbound through Tor. Circuit identity changes. For anything where IP attribution matters — credential testing, lateral movement, probing hostile infra.

⚠️ Tor circuit may not establish on some networks. Deploy papa on a VPS if `torsocks` hangs.

## SSH

Single key, Docker DNS, no IPs.

```bash
ssh root@charlie
ssh root@oscar
ssh root@papa
ssh root@papa "torsocks curl https://ifconfig.me"
```

## Lifecycle

| Worker | Type | Memory | Data safety |
|--------|------|--------|-------------|
| charlie | Disposable | ~500MB | Output on volume — safe to rebuild |
| oscar   | Keep alive | ~1.2GB | Artifacts, compiled exploits, notes |
| papa    | Disposable | ~150MB | Tor state ephemeral, circuit changes on restart |

## Deployment

```bash
# VPS 4GB (mínimo viável):
docker compose up -d                    # charlie + hermes

# Workstation 8GB+ (cluster completo):
docker compose -f docker-compose.yml -f docker-compose.workers.yml --profile full up -d

# Ver status:
docker compose ps
```
