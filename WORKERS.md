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
Alpine. Tor is available through the local SOCKS5 listener. Commands must opt
into the proxy; ordinary outbound traffic is still direct.

```
nmap, python3, curl, tor (SOCKS5 on :9050)
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
ssh root@papa \
  "curl --socks5-hostname 127.0.0.1:9050 https://check.torproject.org/api/ip"
```

## Startup

```bash
./setup.sh
```

The Papa healthcheck validates SSH, SOCKS5, remote DNS through the proxy, and a
Tor exit response.
