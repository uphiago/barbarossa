# Hermes Audit Guardrails Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Hermes ask before falling back from a specifically requested model and constrain controlled capability audits to verified, non-mutating evidence.

**Architecture:** Keep the default DeepSeek Flash configuration unchanged. Add durable Hermes context and skill instructions for explicit-model requests, audit boundaries, and artifact retrieval; configuration only continues to install these files at container startup.

**Tech Stack:** Markdown agent guidance, Python configuration installer, pytest, shell regression checks.

---

### Task 1: Model-request guardrail

**Files:**
- Modify: `AGENTS.md`
- Test: `tests/test-hermes-configure.py`

- [ ] **Step 1: Write the failing test**

Add a test that installs the context and asserts the installed `AGENTS.md` contains both `requested model` and `ask for confirmation`.

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `pytest tests/test-hermes-configure.py -q`

Expected: FAIL because the installed context does not require confirmation for an unavailable requested model.

- [ ] **Step 3: Add the smallest durable instruction**

Add an `Explicit Model Requests` section to `AGENTS.md` requiring Hermes to report the effective model and ask before continuing with a fallback when the user names a model that is not available.

- [ ] **Step 4: Run the focused test and verify it passes**

Run: `pytest tests/test-hermes-configure.py -q`

Expected: PASS.

### Task 2: Controlled audit guardrail

**Files:**
- Modify: `skills/hermes/barbarossa-routing/SKILL.md`
- Modify: `skills/hermes/barbarossa-codex/SKILL.md`
- Test: `tests/infra-regression.sh`

- [ ] **Step 1: Write the failing regression assertions**

Require the routing skill to contain `available but untested`, `skill_manage`, and `job_result`; require the Codex skill to prohibit direct result-path reads during audits.

- [ ] **Step 2: Run the regression check and verify it fails**

Run: `sh tests/infra-regression.sh`

Expected: FAIL because the audit-specific instructions do not exist.

- [ ] **Step 3: Add the smallest instructions**

Require controlled audits to report only executed capabilities as tested, prohibit `skill_manage`, and retrieve artifacts through lifecycle MCP tools rather than direct filesystem reads.

- [ ] **Step 4: Run the regression check and verify it passes**

Run: `sh tests/infra-regression.sh`

Expected: PASS.

### Task 3: Full verification and deployment

**Files:**
- Verify only: `tests/test-hermes-configure.py`, `tests/infra-regression.sh`, `docker-compose.yml`

- [ ] **Step 1: Run all focused Python tests**

Run: `pytest tests/test-hermes-configure.py tests/test-hermes-gateway.py tests/test-worker-rpc.py -q`

Expected: PASS.

- [ ] **Step 2: Run static infrastructure validation**

Run: `sh tests/infra-regression.sh && docker compose config -q`

Expected: both commands exit 0.

- [ ] **Step 3: Publish and deploy through the existing workflow**

Commit the scoped changes, push the branch, open and merge the pull request, then verify the workflow smoke test and deployed Hermes context.

