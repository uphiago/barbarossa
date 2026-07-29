# Configurable Runtime README Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the public README describe Barbarossa as a configurable runtime, document the checked-in deployment as a reference profile, and make the optional GitHub credential work in local setup.

**Architecture:** Keep the executable reference topology unchanged. Separate general architecture from checked-in defaults in documentation, add portable onboarding and extension guidance, and create an empty restricted GitHub token file when local operators do not configure GitHub access.

**Tech Stack:** Markdown, Bash, Docker Compose, Python/YAML regression checks.

---

### Task 1: Make The Optional GitHub Credential Bootable

**Files:**
- Modify: `tests/infra-regression.sh`
- Modify: `setup.sh`

- [ ] **Step 1: Add failing regression assertions**

Add these assertions beside the existing setup/deploy checks:

```sh
grep -Fq 'export BARBAROSSA_GITHUB_TOKEN_FILE=' setup.sh
grep -Fq 'touch "$BARBAROSSA_GITHUB_TOKEN_FILE"' setup.sh
grep -Fq '"$BARBAROSSA_GITHUB_TOKEN_FILE"' setup.sh
```

- [ ] **Step 2: Run the regression test and confirm failure**

Run:

```bash
bash tests/infra-regression.sh
```

Expected: failure because `setup.sh` does not initialize
`BARBAROSSA_GITHUB_TOKEN_FILE`.

- [ ] **Step 3: Initialize the optional secret file**

Add this export with the other runtime paths:

```bash
export BARBAROSSA_GITHUB_TOKEN_FILE="${BARBAROSSA_GITHUB_TOKEN_FILE:-$runtime/github_token}"
```

Create it with the Codex files and include it in the restricted permission
operation:

```bash
touch "$BARBAROSSA_CODEX_AUTH_FILE" "$BARBAROSSA_GITHUB_TOKEN_FILE"
chmod 0644 "$BARBAROSSA_CODEX_TOKEN_FILE" \
  "$BARBAROSSA_CODEX_AUTH_FILE" \
  "$BARBAROSSA_GITHUB_TOKEN_FILE"
```

- [ ] **Step 4: Run focused validation**

Run:

```bash
bash -n setup.sh
bash tests/infra-regression.sh
```

Expected: both commands pass.

- [ ] **Step 5: Commit**

```bash
git add setup.sh tests/infra-regression.sh
git commit -m "fix: initialize optional GitHub worker credential"
```

### Task 2: Reposition The README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Rewrite the introduction**

Define Barbarossa through four stable concepts:

```text
Orchestrator -> typed capabilities -> isolated workers -> durable jobs
```

State that the repository ships a three-container reference profile rather than
defining three containers as an architectural requirement.

- [ ] **Step 2: Add a Reference Profile section**

Document the checked-in defaults explicitly:

```text
Hermes: DeepSeek V4 Flash, up to three child tasks
Forge runtime: one general execution lane
Forge Codex: GPT-5.6 Luna medium, one internal subagent
Recon: one network lane, direct or explicit Tor
```

Clarify that providers, models, worker types, and concurrency policies can be
changed by editing the runtime configuration and capability contracts.

- [ ] **Step 3: Add portable onboarding**

Include:

```bash
git clone https://github.com/uphiago/barbarossa.git
cd barbarossa
cp .env.example .env
./setup.sh
```

Explain Codex authentication, the optional GitHub token file, Telegram pairing,
static allowlists, and a generic dashboard tunnel:

```bash
ssh -NL 9119:127.0.0.1:9119 user@server
```

- [ ] **Step 4: Correct verification and production claims**

Use a portable smoke command:

```bash
cd /path/to/barbarossa
scripts/smoke-remote.sh
```

Remove the Git-history secret-scan claim. Describe the workflow as testing,
building, publishing immutable images, verifying the deployment SSH host key,
deploying, and running remote smoke tests.

- [ ] **Step 5: Add extension guidance**

Document the required extension chain:

```text
Compose service
  -> worker RPC capability
  -> MCP router tool
  -> Hermes routing instruction
  -> smoke test
```

State that workers are not discovered dynamically.

- [ ] **Step 6: Validate README accuracy**

Run:

```bash
! rg -n 'portable three-container|scans Git history|ssh ovh' README.md
rg -n 'reference profile|pairing|MCP|worker RPC|smoke' README.md
git diff --check
```

Expected: stale claims are absent, new concepts are present, and formatting is
clean.

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs: present Barbarossa as a configurable runtime"
```

### Task 3: Final Verification

**Files:**
- Verify: `README.md`
- Verify: `setup.sh`
- Verify: `tests/infra-regression.sh`

- [ ] **Step 1: Run all non-container regression tests**

```bash
uv run --with pytest==9.1.1 --with pyyaml==6.0.3 \
  pytest tests/test-worker-rpc.py tests/test-hermes-configure.py -q
uv run --with pyyaml==6.0.3 bash tests/infra-regression.sh
```

Expected: all tests pass.

- [ ] **Step 2: Validate Compose with temporary secret files**

Run the same `docker compose config --quiet` fixture used by the GitHub Actions
`validate` job, with temporary files for every Compose secret.

Expected: Compose validation exits successfully.

- [ ] **Step 3: Review the final diff**

```bash
git diff origin/main...HEAD --check
git status --short
git log --oneline origin/main..HEAD
```

Expected: no whitespace errors, a clean worktree, and only the design, plan,
setup regression, and README commits.
