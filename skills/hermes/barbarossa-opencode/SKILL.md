---
name: barbarossa-opencode
description: Delegate multi-agent engineering jobs to the Forge OpenCode lane on the free DeepSeek model.
---

# Barbarossa OpenCode

Stage every attachment beneath `/opt/data/barbarossa-transfer` before calling a
Forge tool. Pass only staged absolute paths to the router.

- Use `code_opencode` for multi-agent engineering: parallel reconnaissance,
  independent implementation tracks, and verification sprints. One job
  orchestrates up to ten parallel subagents (`explorer`, `implementer`,
  `tester`, `reviewer`) on the free `deepseek-v4.1-flash-free` model.
- Optionally set `opencode_variant` to `low`, `high` (default), or `max` to
  trade latency for reasoning depth. Codex profiles do not apply to this tool.
- Prefer `code_delegate` when the task needs the configured Codex profile, or
  image understanding and generation.
- Poll the returned job rather than starting another copy.
- Accept result paths only beneath `/opt/data/barbarossa-results/<job_id>` and
  read them through `job_result`, never with `read_file` or the terminal.
- The free tier is temporary and needs no credentials: when `code_opencode`
  jobs fail on free-tier errors, fall back to `code_delegate` and report the
  fallback.
