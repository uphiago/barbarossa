# Forge Gmail Secrets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Forge worker receive the Gmail Docker secrets required by the existing `gmail_read` and `gmail_send` capabilities.

**Architecture:** Forge starts as root, stages a small allowlist of Docker secrets under `/run/barbarossa-secrets` with ownership restricted to the `forge` user, then starts the worker. The mail job code already resolves secrets from that directory; the entrypoint allowlist is the missing link.

**Tech Stack:** POSIX shell, Docker secrets, Docker Compose, pytest/bash infrastructure tests, GitHub Actions deployment.

---

### Task 1: Lock the Gmail secret staging contract with a failing regression test

**Files:**
- Modify: `tests/infra-regression.sh`
- Test: `tests/infra-regression.sh`

- [ ] Add an assertion that the Forge entrypoint stages `github_token`, `gmail_user`, and `gmail_app_password`.

```bash
grep -Fq 'for secret in github_token gmail_user gmail_app_password; do' \
  containers/forge/forge-entrypoint.sh
```

- [ ] Run `uv run --with pyyaml==6.0.3 bash tests/infra-regression.sh` and confirm it fails because the entrypoint still lists only `github_token`.

### Task 2: Stage the Gmail secrets in Forge

**Files:**
- Modify: `containers/forge/forge-entrypoint.sh`
- Test: `tests/infra-regression.sh`

- [ ] Replace the one-item allowlist with:

```sh
for secret in github_token gmail_user gmail_app_password; do
```

- [ ] Re-run `uv run --with pyyaml==6.0.3 bash tests/infra-regression.sh` and confirm it passes.

### Task 3: Validate and publish the Forge image

**Files:**
- Verify: `tests/test-worker-rpc.py`
- Verify: `tests/test-hermes-configure.py`
- Verify: `tests/test-hermes-secret-stage.sh`
- Verify: `tests/infra-regression.sh`

- [ ] Run the full worker/infrastructure validation:

```bash
uv run --with pytest==9.1.1 --with pyyaml==6.0.3 \
  pytest tests/test-worker-rpc.py tests/test-hermes-configure.py -q
tests/test-hermes-secret-stage.sh
uv run --with pyyaml==6.0.3 bash tests/infra-regression.sh
```

- [ ] Commit only the Gmail staging fix, its regression test, and the already-approved Listmonk operational documentation.
- [ ] Push the branch/tag that triggers `.github/workflows/build-deploy.yml`, then wait for its validate, worker build, and OVH deploy jobs.

### Task 4: Verify the OVH runtime

**Files:**
- Verify only: deployed `barbarossa-forge-1`

- [ ] Confirm the staged files exist with `0600 forge:forge` ownership without printing their contents.
- [ ] Ask Hermes to read a small inbox sample.
- [ ] Ask Hermes to prepare a direct email, show the final recipient/subject/body, then send only after the operator's second confirmation.
