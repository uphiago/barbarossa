# COP — Agent Routing Guide

CHARLIE collects. OSCAR operates. PAPA persists. Three phases, one cluster.

## Decision Matrix

| You need to... | Worker | Why |
|---------------|--------|-----|
| Discover subdomains, probe live hosts | **charlie** | All scanning tools |
| Run nuclei, fuzz parameters | **charlie** | Fast, parallel |
| Port scan, service detection | **charlie** | nmap + scripts |
| JS bundle scraping, secret extraction | **charlie** | Python + curl |
| Analyze a suspicious binary | **oscar** | Only worker with gdb, xxd, file |
| Compile a PoC exploit | **oscar** | Only worker with gcc, make |
| Debug via core dump / strace | **oscar** | RE toolchain |
| Probe hostile target anonymously | **papa** | Tor SOCKS5 |
| Bypass geo-blocks / rate limits | **papa** | Different exit IP |
| Credential testing without burning IP | **papa** | Circuit changes |

## Workers

### charlie (collect)
Alpine. All scanning tools. Disposable — rebuild anytime. Output on volume.

```
nmap, masscan, subfinder, httpx, dnsx, nuclei,
ffuf, naabu, katana, amass, python3, curl, dig
```

### oscar (operate)
Debian. Full recon toolset + RE/compilation. Stateful — keep exploits here.

```
Everything from charlie PLUS:
gdb, gcc, g++, make, cmake, strace, ltrace, xxd,
file, socat, jq, full Python with all libs
```

### papa (persist)
Alpine. All outbound through Tor. Disposable — circuit changes on restart.

```
nmap, python3, curl, subfinder, Tor SOCKS5 on :9050
```

## Flow

```
charlie → map the surface → subdomains, live hosts, vulnerabilities
oscar   → exploit the vuln → compile PoC, launch, get shell
papa    → pivot from shell → lateral movement, stay hidden
charlie → re-scan inside   → new perspective, repeat
```

## SSH

```bash
ssh root@charlie
ssh root@oscar
ssh root@papa
ssh root@papa "torsocks curl https://ifconfig.me"
```

## Startup

```bash
docker compose up -d   # sobe todos os workers + hermes, cabe em 4GB
```

⚠️ Papa usa Tor. Se `torsocks` travar, o circuito Tor nao estabelece nessa rede — implante em VPS.
