---
name: barbarossa-codex
description: Delegate code and image jobs to the isolated Forge Codex lane.
---

# Barbarossa Codex

Stage every attachment beneath `/opt/data/barbarossa-transfer` before calling a
Forge tool. Pass only staged absolute paths to the router.

- For inbound image attachments already staged by the gateway, call
  `media_image_inspect` immediately with the complete accompanying user
  request as its `prompt`. Do not call `vision_analyze`, auxiliary vision
  providers, or the terminal command `file`.
- Use `code_delegate` for repository analysis, implementation, review, and
  tests.
- Use `media_image_inspect` to understand an existing image.
- Use `media_image_generate` to create a new image.
- Use `media_image_edit` with exactly one staged input image.
- Poll the returned job rather than starting another copy.
- Accept result paths only beneath `/opt/data/barbarossa-results/<job_id>`.
- Do not read artifacts directly with `read_file` or the terminal. Use
  `job_result` after a terminal job status, then summarize the returned
  artifact metadata or content.

Forge receives its Codex model, reasoning effort, and internal subagent limit
from the deployment profile. For a Codex job, select a profile only when the task benefits from that model.
They ascend in capability: `fast` uses **Luna**, `balanced` uses **Terra**,
`deep` uses **Sol** (all three at `high` reasoning), and `astra` uses
**Astra** — the newest generation, at `xhigh`. Reach for `astra` when the work
is a full audit or a genuinely hard question; `high` is right for the rest.
Omit the profile to use the deployment default. Promote valuable
source or artifacts to a private Git repository manually; worker state remains
disposable.
