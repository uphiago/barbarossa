---
name: barbarossa-artifacts
description: Keep Forge job outputs inside the durable per-job output directory.
---

# Barbarossa Artifacts

Work only inside the current job directory.

- Read staged inputs from `inputs/`.
- Write final deliverables to `outputs/`.
- Keep source repositories and temporary build files inside the job directory.
- Never write credentials, authentication caches, or secret values to outputs.
- Do not remove job logs, request metadata, or previous outputs.
- For image generation or editing, use `$imagegen` and save the final raster
  image under `outputs/`.
