# OVH Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the confirmed OVH host and container attack surface without rotating SSH keys or breaking the Hermes tunnel and worker workflows.

**Architecture:** Apply host controls independently from Compose controls. Every host change gets a timed rollback and an independent SSH verification before it is made persistent; every Compose change is tested locally and deployed one service at a time before the full stack is accepted.

**Tech Stack:** Ubuntu 26.04 LTS, OpenSSH 10.2, UFW/nftables, Fail2ban, Docker Engine 29, Docker Compose, Bash.

---

### Task 1: Baseline And Recovery

**Files:**
- Create locally outside the repository: `~/.local/state/barbarossa/backups/<timestamp>/`
- Create remotely: `/root/barbarossa-hardening-backup-<timestamp>/`

- [x] Capture effective SSH, UFW, Fail2ban, nftables, Docker, services, listeners, account and container state.
- [x] Copy host configuration and Barbarossa runtime configuration to a root-only remote rollback directory.
- [x] stream an archive of the remote rollback directory to the root-only local backup directory.
- [x] Verify the local archive can be listed and contains no unreadable files.
- [x] Open a second independent key-only SSH connection before any access-control change.

### Task 2: Block Container Access To OVH Metadata

**Files:**
- Create: `ops/host/barbarossa-container-firewall`
- Create: `ops/host/barbarossa-container-firewall.service`
- Create: `/usr/local/sbin/barbarossa-container-firewall`
- Create: `/etc/systemd/system/barbarossa-container-firewall.service`

- [x] Schedule a five-minute rollback unit before installing firewall rules.
- [x] Add idempotent IPv4 and IPv6 rules in `DOCKER-USER` that reject metadata destinations.
- [x] Start and enable the service after Docker and network availability.
- [x] Confirm every container fails to read the metadata endpoint.
- [x] Confirm Charlie and Oscar retain direct Internet access.
- [x] Confirm Papa reaches the Internet through Tor.
- [x] Confirm Hermes dashboard, Telegram-related logs and worker SSH remain healthy.
- [x] Cancel the rollback only after a fresh SSH connection succeeds.

### Task 3: Neutralize The Exposed Unix Password

**Files:**
- Modify host account state for `ubuntu`; do not change `authorized_keys`.

- [x] Confirm `PasswordAuthentication no` and `KbdInteractiveAuthentication no` effectively.
- [x] Confirm root is locked, `ubuntu` has key-only SSH access and passwordless sudo works.
- [x] Schedule a rollback that unlocks `ubuntu` if access validation fails.
- [x] Lock the Unix password for `ubuntu`.
- [x] Verify a fresh key-only SSH session, sudo, Docker access, Hermes tunnel and GitHub deploy prerequisites.
- [x] Cancel the rollback after all access tests pass.

### Task 4: Restrict SSH Forwarding

**Files:**
- Create: `ops/host/48-barbarossa-forwarding.conf`
- Create: `/etc/ssh/sshd_config.d/48-barbarossa-forwarding.conf`

- [x] Add `X11Forwarding no`, `AllowAgentForwarding no`, `AllowTcpForwarding local`, `PermitOpen 127.0.0.1:9119 localhost:9119`, `LogLevel VERBOSE`, and `RequiredRSASize 3072`.
- [x] Validate with `sshd -t` and inspect the effective configuration with `sshd -T`.
- [x] Schedule rollback before reloading SSH.
- [x] Reload SSH without terminating existing sessions.
- [x] Verify a fresh SSH session and the configured local Hermes tunnel.
- [x] Verify remote forwarding and an unrelated local destination are rejected.
- [x] Cancel rollback after validation.

### Task 5: Make Fail2ban Runtime Match Configuration

**Files:**
- Create: `ops/host/fail2ban-sshd.local`
- Modify: `/etc/fail2ban/jail.d/sshd.local`

- [x] Preserve the existing SSH jail and add bounded incremental ban settings.
- [x] Validate configuration using `fail2ban-client -t`.
- [x] Reload Fail2ban and confirm the runtime values, journal backend and nftables action.
- [x] Confirm the administrative IP is not banned and a fresh SSH login succeeds.

### Task 6: Add Basic Docker Containment

**Files:**
- Modify: `docker-compose.yml`
- Modify: `tests/infra-regression.sh`

- [x] Add regression assertions for four healthchecks, bounded Docker logs, PID limits and `no-new-privileges`.
- [x] Run the regression test and confirm the new assertions fail.
- [x] Add log rotation to every service.
- [x] Add conservative PID and memory limits based on observed production use.
- [x] Add `no-new-privileges:true` and a dashboard healthcheck.
- [x] Validate the rendered Compose configuration.
- [x] Run regression tests and confirm all assertions pass.
- [x] Deploy and validate Charlie, Oscar, Papa and Hermes progressively.

### Task 7: Remove Unneeded Host Services Carefully

**Files:**
- Modify host service enablement only after dependency inspection.

- [x] Inspect reverse dependencies and logs for ModemManager and udisks2.
- [x] Disable only services with no Barbarossa, OVH console or storage dependency.
- [x] Confirm listeners, Docker, SSH, networking and qemu-guest-agent remain healthy.
- [x] Record intentionally retained services.

### Task 8: Final Audit And Documentation

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `../AGENTS.md`

- [x] Update the documented OS to Ubuntu 26.04 LTS.
- [x] Document the container metadata boundary, SSH forwarding restriction, password lock and rollback locations.
- [x] Run repository tests and inspect the final diff.
- [x] Verify SSH, tunnel, dashboard, worker SSH, Tor, UFW, Fail2ban, automatic updates, AppArmor, Docker health and logs.
- [x] Review authentication, Fail2ban and container logs for regressions.
- [x] Record deferred work: external encrypted backups, forced-Tor egress and deeper capability reduction.

## Completion Evidence

- Rollback backup verified locally under
  `~/.local/state/barbarossa/backups/20260727T222408Z/` and remotely under
  `/root/barbarossa-hardening-backup-20260727T222408Z/`.
- Container hardening deployed by GitHub Actions run `30311306795`.
- Immutable Node 24 Actions validated by GitHub Actions run `30311574698`.
- Final audit confirmed key-only SSH, the Hermes tunnel, metadata blocking,
  Fail2ban, UFW, AppArmor, automatic updates, four healthy containers, Tor,
  dashboard access, worker SSH, bounded logs and resource limits.
