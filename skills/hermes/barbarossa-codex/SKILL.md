---
name: barbarossa-codex
description: Delegate code and image jobs to the isolated Forge Codex lane.
---

# Barbarossa Codex

Stage every attachment beneath `/opt/data/barbarossa-transfer` before calling a
Forge tool. Pass only staged absolute paths to the router.

- Use `code_delegate` for repository analysis, implementation, review, and
  tests.
- Use `media_image_inspect` to understand an existing image.
- Use `media_image_generate` to create a new image.
- Use `media_image_edit` with exactly one staged input image.
- Poll the returned job rather than starting another copy.
- Accept result paths only beneath `/opt/data/barbarossa-results/<job_id>`.

Forge runs Codex GPT-5.6 Luna at medium reasoning. Codex may use one internal
subagent when useful. Promote valuable source or artifacts to a private Git
repository manually; worker state remains disposable.
