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

- [ ] Capture effective SSH, UFW, Fail2ban, nftables, Docker, services, listeners, account and container state.
- [ ] Copy host configuration and Barbarossa runtime configuration to a root-only remote rollback directory.
- [ ] stream an archive of the remote rollback directory to the root-only local backup directory.
- [ ] Verify the local archive can be listed and contains no unreadable files.
- [ ] Open a second independent key-only SSH connection before any access-control change.

### Task 2: Block Container Access To OVH Metadata

**Files:**
- Create: `ops/host/barbarossa-container-firewall`
- Create: `ops/host/barbarossa-container-firewall.service`
- Create: `/usr/local/sbin/barbarossa-container-firewall`
- Create: `/etc/systemd/system/barbarossa-container-firewall.service`

- [ ] Schedule a five-minute rollback unit before installing firewall rules.
- [ ] Add idempotent IPv4 and IPv6 rules in `DOCKER-USER` that reject metadata destinations.
- [ ] Start and enable the service after Docker and network availability.
- [ ] Confirm every container fails to read the metadata endpoint.
- [ ] Confirm Charlie and Oscar retain direct Internet access.
- [ ] Confirm Papa reaches the Internet through Tor.
- [ ] Confirm Hermes dashboard, Telegram-related logs and worker SSH remain healthy.
- [ ] Cancel the rollback only after a fresh SSH connection succeeds.

### Task 3: Neutralize The Exposed Unix Password

**Files:**
- Modify host account state for `ubuntu`; do not change `authorized_keys`.

- [ ] Confirm `PasswordAuthentication no` and `KbdInteractiveAuthentication no` effectively.
- [ ] Confirm root is locked, `ubuntu` has key-only SSH access and passwordless sudo works.
- [ ] Schedule a rollback that unlocks `ubuntu` if access validation fails.
- [ ] Lock the Unix password for `ubuntu`.
- [ ] Verify a fresh key-only SSH session, sudo, Docker access, Hermes tunnel and GitHub deploy prerequisites.
- [ ] Cancel the rollback after all access tests pass.

### Task 4: Restrict SSH Forwarding

**Files:**
- Create: `ops/host/48-barbarossa-forwarding.conf`
- Create: `/etc/ssh/sshd_config.d/48-barbarossa-forwarding.conf`

- [ ] Add `X11Forwarding no`, `AllowAgentForwarding no`, `AllowTcpForwarding local`, `PermitOpen 127.0.0.1:9119 localhost:9119`, `LogLevel VERBOSE`, and `RequiredRSASize 3072`.
- [ ] Validate with `sshd -t` and inspect the effective configuration with `sshd -T`.
- [ ] Schedule rollback before reloading SSH.
- [ ] Reload SSH without terminating existing sessions.
- [ ] Verify a fresh SSH session and the configured local Hermes tunnel.
- [ ] Verify remote forwarding and an unrelated local destination are rejected.
- [ ] Cancel rollback after validation.

### Task 5: Make Fail2ban Runtime Match Configuration

**Files:**
- Create: `ops/host/fail2ban-sshd.local`
- Modify: `/etc/fail2ban/jail.d/sshd.local`

- [ ] Preserve the existing SSH jail and add bounded incremental ban settings.
- [ ] Validate configuration using `fail2ban-client -t`.
- [ ] Reload Fail2ban and confirm the runtime values, journal backend and nftables action.
- [ ] Confirm the administrative IP is not banned and a fresh SSH login succeeds.

### Task 6: Add Basic Docker Containment

**Files:**
- Modify: `docker-compose.yml`
- Modify: `tests/infra-regression.sh`

- [ ] Add regression assertions for four healthchecks, bounded Docker logs, PID limits and `no-new-privileges`.
- [ ] Run the regression test and confirm the new assertions fail.
- [ ] Add log rotation to every service.
- [ ] Add conservative PID and memory limits based on observed production use.
- [ ] Add `no-new-privileges:true` and a dashboard healthcheck.
- [ ] Validate the rendered Compose configuration.
- [ ] Run regression tests and confirm all assertions pass.
- [ ] Deploy and validate Charlie, Oscar, Papa and Hermes progressively.

### Task 7: Remove Unneeded Host Services Carefully

**Files:**
- Modify host service enablement only after dependency inspection.

- [ ] Inspect reverse dependencies and logs for ModemManager and udisks2.
- [ ] Disable only services with no Barbarossa, OVH console or storage dependency.
- [ ] Confirm listeners, Docker, SSH, networking and qemu-guest-agent remain healthy.
- [ ] Record intentionally retained services.

### Task 8: Final Audit And Documentation

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `../AGENTS.md`

- [ ] Update the documented OS to Ubuntu 26.04 LTS.
- [ ] Document the container metadata boundary, SSH forwarding restriction, password lock and rollback locations.
- [ ] Run repository tests and inspect the final diff.
- [ ] Verify SSH, tunnel, dashboard, worker SSH, Tor, UFW, Fail2ban, automatic updates, AppArmor, Docker health and logs.
- [ ] Review authentication, Fail2ban and container logs for regressions.
- [ ] Record deferred work: external encrypted backups, forced-Tor egress and deeper capability reduction.
