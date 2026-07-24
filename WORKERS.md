# Worker Cluster — Agent Routing Guide

Three specialized workers. Not "three copies with different tools" — three different execution environments for different phases of an operation.

## Decision Matrix

| You need to... | Use | Why |
|---------------|------|-----|
| Discover subdomains, probe live hosts | **worker** | Fast, all scanning tools |
| Run nuclei templates, fuzz parameters | **worker** | Mass scanning, parallel |
| Quick curl/HTTP probes | **worker** | Lightweight |
| Port scan, service detection, OS fingerprint | **worker** | nmap + scripts |
| Scrape JS bundles, extract secrets | **worker** | Python + curl |
| **Analyze a suspicious binary** from a target | **worker-heavy** | Only worker with gdb, xxd, file |
| **Compile a PoC exploit** from source | **worker-heavy** | Only worker with gcc, make |
| **Debug a crashing service** via core dump | **worker-heavy** | Only worker with gdb + strace |
| **Reverse engineer a malware sample** | **worker-heavy** | Binutils + Python full |
| **Probe a hostile target anonymously** | **worker-tor** | Traffic routed through Tor |
| **Bypass geo-blocks or IP rate limits** | **worker-tor** | Different exit IP per circuit |
| **Recon on a target that is actively monitoring** | **worker-tor** | Don't burn your real IP |

## Workers

### worker (recon)
Fast, disposable. Alpine. All scanning tools. This is the default — most tasks run here.

```
nmap, masscan, subfinder, httpx, dnsx, nuclei,
ffuf, naabu, katana, amass, python3, curl, dig
```

### worker-heavy (analysis + RE)
Persistent. Don't treat as disposable — keep compiled exploits, analysis notes, extracted binaries here.

```
Everything from worker PLUS:
gdb, gcc, g++, make, cmake, strace, ltrace, xxd,
file, socat, jq, full Python with all libs
```

### worker-tor (anonymous)
All outbound traffic through Tor. Circuit identity changes over time. For anything where IP attribution matters.

```
nmap, python3, curl, subfinder, Tor SOCKS5 on :9050
```

⚠️ Tor circuit may not establish on some networks. If `torsocks` hangs, deploy this worker on a VPS.

## Operation Flow Example

```
1. worker:     subfinder -d target.com → 15 subdomains
2. worker:     httpx -l subs.txt → 12 live, 3 dead
3. worker:     nuclei on live hosts → finds WordPress + Exchange
4. worker:     wpscan on WordPress → plugin CVE found
5. worker-heavy: compile CVE exploit from GitHub → binary ready
6. worker-tor:  test exploit against target anonymously
7. worker:     if exploit works, full scan from worker
```

## SSH

Single key, all workers. Docker DNS resolves hostnames — no IPs to remember.

```bash
ssh root@worker
ssh root@worker-heavy
ssh root@worker-tor
```

## Tor Usage

```bash
# Wrap commands with torsocks:
ssh root@worker-tor "torsocks curl -s https://ifconfig.me"

# Or SOCKS5 proxy directly:
curl --socks5-hostname worker-tor:9050 https://target.com
```

## Lifecycle

| Worker | Lifecycle | Data |
|--------|-----------|------|
| **worker** | Disposable. Rebuild anytime | `/root/output` is a volume — persists across rebuilds |
| **worker-heavy** | Keep alive. Stateful | Compile artifacts, notes, exploit binaries |
| **worker-tor** | Disposable. Circuit changes on restart | Tor state is ephemeral |
