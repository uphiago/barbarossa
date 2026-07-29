# Configurable Runtime README Design

## Goal

Reposition Barbarossa as a configurable capability-oriented agent runtime while
keeping the repository's current Hermes, Forge, and Recon deployment documented
as a concrete reference profile.

## Content Structure

1. Introduce the general orchestrator, worker, capability, and job model.
2. Present Hermes, Forge, Recon, DeepSeek, Codex, and concurrency values under
   a clearly labeled reference profile.
3. Retain the capability, image, state, security, verification, and production
   documentation that matches the implementation.
4. Add a portable quick start, Telegram authorization guidance, and an
   extension contract.

## Accuracy Requirements

- Do not claim that the architecture requires a particular model, provider,
  worker count, or concurrency limit.
- State that the checked-in configuration currently uses DeepSeek V4 Flash,
  three Hermes child tasks, Codex GPT-5.6 Luna medium, and one Codex subagent.
- Explain that adding a worker or capability requires explicit Compose, worker
  RPC, MCP router, routing instruction, and smoke-test changes.
- Describe SSH as restricted internal transport and MCP as the agent-facing
  contract.
- Remove the false claim that GitHub Actions scans Git history for secrets.
- Use generic SSH commands before environment-specific `ssh ovh` examples.
- Explain Telegram pairing and static allowlist modes.
- Keep secrets and environment-specific identifiers out of the document.

## Supporting Setup Correction

The local setup describes the GitHub credential as optional. Ensure the setup
creates the configured GitHub token file when it is absent so Docker Compose
can mount an empty secret without making GitHub access mandatory.

## Verification

- Run shell syntax validation for `setup.sh`.
- Run infrastructure regression and configuration tests.
- Validate Docker Compose with temporary external secret files.
- Scan the README for stale claims and environment-specific commands.
- Run `git diff --check`.
