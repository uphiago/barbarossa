---
name: barbarossa-routing
description: Route work to the isolated Forge and Recon jobs exposed by Barbarossa.
---

# Barbarossa Routing

Use Barbarossa jobs for execution. Hermes plans, delegates, tracks, and
combines results; it does not perform heavy execution in its own container.

- Use `runtime_execute` for generic shell, compilation, and file work.
- Use `code_delegate` for engineering work that benefits from Codex.
- Use the media tools only for file inspection and image inspect/generate/edit.
- Use Recon directly by default. Use `network_tor` only when the request
  explicitly requires Tor.
- After submission, poll `job_status`. Do not submit duplicates because a log
  is empty or a job is still running.
- Use `job_logs` for progress, but never infer success from an empty log.
- Use `job_result` only after a terminal status.

Hermes may run up to three independent child agents in parallel. Parallelize
independent Forge runtime, Forge Codex, and Recon work; keep dependent work
sequential.

## Controlled Capability Audits

- A capability is available but untested until a completed job provides
  evidence for that exact capability. Report available but untested separately
  from tested capabilities.
- Do not use `skill_manage` during an audit. Do not modify skills, global
  configuration, credentials, containers, or persistent files unless the user
  explicitly asks for that change.
- Retrieve job outputs through `job_status`, `job_logs`, and `job_result`.
  Do not use `read_file` or the terminal to inspect result paths directly.
- When an audit requests a model that is not the effective model, follow the
  explicit-model rule in `AGENTS.md` before submitting any jobs.
