# Barbarossa Runtime Guide

Barbarossa has three containers and three independent execution lanes:

```text
Hermes
├── Forge / runtime
├── Forge / Codex
└── Recon
```

## Forge

Forge is a non-root engineering environment. Its runtime and Codex lanes can
run concurrently, but each lane admits one job at a time.

| Capability | Lane | Use |
| --- | --- | --- |
| `runtime.execute` | runtime | Shell, builds, conversions, general tooling |
| `media.file.inspect` | runtime | File type and MIME inspection |
| `code.delegate` | codex | Repository engineering through Codex |
| `media.image.inspect` | codex | Read an image |
| `media.image.generate` | codex | Generate an image with `$imagegen` |
| `media.image.edit` | codex | Edit one staged image |

The Codex model, reasoning effort, and internal subagent limit are supplied by
the deployment profile.
The outer Forge container is its sandbox boundary.

## Recon

Recon admits one network job at a time and contains the consolidated discovery
toolkit. Direct egress and Tor are distinct capabilities:

| Capability | Route |
| --- | --- |
| `network.fetch` | Direct HTTP(S), fixed curl argv |
| `network.inspect` | Direct authorized command |
| `network.tor` | Explicit `torsocks --isolate` command |

Tor listens only on `127.0.0.1:9050` inside Recon. It is not published and is
never selected automatically.

## Job Files

Each worker retains:

```text
/workspace/jobs/<job_id>/
├── inputs/
├── outputs/
├── request.json
├── status.json
├── stdout.log
├── stderr.log
└── result.json
```

Hermes retains its queue database, transfer area, and downloaded results in
its own named volume. No scheduled cleanup or backup is configured.
