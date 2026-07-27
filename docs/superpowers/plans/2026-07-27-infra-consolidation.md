# Infra Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `barbarossa` the only worker-infrastructure source, with clean local and production key bootstraps, supervised Tor, persistent SSH identity, healthchecks, and reproducible tool downloads.

**Architecture:** Local development continues through `setup.sh`; production receives a base64-encoded worker key through GitHub Actions and stores runtime material outside the clone. Docker Compose mounts the selected public key, persists worker host keys, and gates Hermes on worker health. The obsolete outer Compose and worker images are removed.

**Tech Stack:** Bash, Docker Compose, Dockerfiles, GitHub Actions, OpenSSH, Tor

---

### Task 1: Regression test harness

**Files:**
- Create: `tests/infra-regression.sh`

- [x] **Step 1: Write assertions for required dashboard variables, external authorized-keys path, worker healthchecks, persistent host-key volumes, supervised Tor, production key secret handling, checksummed downloads, and absence of weak defaults.**

- [x] **Step 2: Run `bash tests/infra-regression.sh` and verify it fails against the current configuration.**

- [x] **Step 3: Commit the failing regression test.**

### Task 2: Separate local and production bootstrap

**Files:**
- Modify: `.env.example`
- Modify: `setup.sh`
- Modify: `.github/workflows/build-deploy.yml`
- Modify: `docker-compose.yml`

- [x] **Step 1: Make `setup.sh` validate non-empty dashboard configuration and keep local keys under `BARBAROSSA_SSH_KEY`.**

- [x] **Step 2: Add `BARBAROSSA_AUTHORIZED_KEYS_FILE` to Compose and mount that external public-key file into every worker.**

- [x] **Step 3: Add production workflow handling for `BARBAROSSA_WORKER_SSH_KEY_B64`: decode under `~/.config/barbarossa`, validate with `ssh-keygen`, derive `authorized_keys`, persist the public path in `.env`, deploy, then atomically install the private key into Hermes.**

- [x] **Step 4: Require `DASHBOARD_USER`, `DASHBOARD_PASS`, and `DASHBOARD_SECRET` in Compose without fallback values.**

- [x] **Step 5: Run the regression test and Compose config with explicit non-secret test values.**

### Task 3: Worker lifecycle and health

**Files:**
- Modify: `docker-compose.yml`
- Modify: `workers/shared/worker-entrypoint.sh`
- Modify: `workers/papa/tor-entrypoint.sh`
- Modify: `workers/papa/Dockerfile`

- [x] **Step 1: Add dedicated `/etc/ssh` volumes for Charlie, Oscar, and Papa so host keys survive recreation.**

- [x] **Step 2: Add SSH healthchecks to Charlie and Oscar, plus SSH-and-SOCKS healthchecking to Papa; gate Hermes with `condition: service_healthy`.**

- [x] **Step 3: Make Papa's entrypoint start Tor and SSH as children, wait for the SOCKS listener, propagate signals, and exit if either child stops.**

- [x] **Step 4: Configure a Tor `DataDirectory`, run Tor as its packaged non-root user, and use `curl --socks5-hostname` for circuit validation.**

- [x] **Step 5: Run shell syntax tests, regression tests, and a focused Papa image build.**

### Task 4: Reproducible worker tool downloads

**Files:**
- Modify: `workers/charlie/Dockerfile`
- Modify: `workers/oscar/Dockerfile`

- [x] **Step 1: Replace `curl -sL` with `curl -fsSL` and verify every downloaded archive against a pinned SHA-256 before extraction.**

- [x] **Step 2: Pin Amass to `v5.1.1` instead of its mutable `latest` URL.**

- [x] **Step 3: Remove Oscar's `2>/dev/null || true` so Python dependency failures stop the build.**

- [x] **Step 4: Build Charlie and Oscar images and confirm required binaries report versions.**

### Task 5: Documentation and duplicate removal

**Files:**
- Modify: `README.md`
- Modify: `WORKERS.md`
- Modify: `AGENTS.md`
- Modify: `../AGENTS.md`
- Delete: `../images/`
- Delete: `../compose/`

- [x] **Step 1: Document local setup separately from production GitHub Actions deployment, including the new worker-key secret.**

- [x] **Step 2: Replace stored dashboard credentials and invalid host SSH examples with environment-driven instructions and `127.0.0.1:2222`.**

- [x] **Step 3: Document `curl --socks5-hostname 127.0.0.1:9050` as Papa's verified Tor path.**

- [x] **Step 4: Remove the duplicate outer Compose, worker Dockerfiles, and committed worker key material.**

- [x] **Step 5: Verify `agent-image-bench` has no changes.**

### Task 6: Production-safe verification

**Files:**
- Modify: none

- [x] **Step 1: Generate a new ED25519 worker key under `~/.ssh`, outside all repositories, and produce its one-line base64 secret value without printing the private key.**

- [x] **Step 2: Run all local regression, syntax, Compose, build, and secret scans.**

- [x] **Step 3: Inspect the final Git diff and commit implementation changes.**

- [x] **Step 4: Recheck OVH container status and logs without deploying or rotating the active key.**

