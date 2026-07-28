# Barbarossa Worker Architecture

Date: 2026-07-28

## Objective

Replace the current Hermes, Charlie, Oscar, and Papa deployment with a
portable three-container architecture:

- `hermes`: the DeepSeek-powered orchestrator.
- `forge`: the general runtime and Codex execution environment.
- `recon`: the isolated network operations environment.

The deployment is intentionally disposable. Local sessions, job workspaces,
and tool state may be lost when the stack moves to another host. Configuration,
skills, and selected artifacts become durable only after they are committed to
Git.

Audio processing is outside the initial scope.

## Design Principles

1. Hermes plans, delegates, tracks jobs, and combines results. It does not run
   worker workloads directly.
2. Capabilities are logical interfaces, not containers.
3. Forge and Recon have separate credentials, networks, and filesystems.
4. Workers never receive the Docker socket or host-level access.
5. Images, configuration, and skills are reproducible; operational state is
   disposable.
6. Resource admission is explicit so parallel agents cannot exhaust the OVH
   host.

## Architecture

```text
Telegram / API
      |
      v
+-----------------------------+
|           Hermes            |
| DeepSeek V4 Flash           |
| planning, delegation, jobs  |
| barbarossa-router MCP       |
+-------------+---------------+
              |
       SSH over isolated
       control networks
        /             \
       v               v
+-------------+   +-------------+
|    Forge    |   |    Recon    |
| runtime     |   | direct net  |
| Codex       |   | optional Tor|
| image tools |   | recon tools |
+-------------+   +-------------+
```

The Compose project is named `barbarossa`. Services do not set
`container_name`, allowing Compose to generate portable names.

Hermes joins two independent internal control networks:

- `hermes-forge`
- `hermes-recon`

Forge and Recon do not share a network. Worker SSH ports are reachable only
inside their respective control networks and are never published on the host.

## Components

### Hermes

Hermes remains based on the official upstream image. Its primary model and
native delegated agents use DeepSeek V4 Flash. Native delegation is enabled
with at most three Hermes children.

Hermes runs `barbarossa-router` as an MCP stdio process. CI produces a
read-only router runtime bundle with locked dependencies, which the deployment
mounts into the official Hermes container. This avoids maintaining a fork of
the Hermes image.

The router is the only component that holds worker control credentials. It
performs admission control, stages job inputs, invokes worker commands through
SSH, tracks processes, and validates structured results.

### Forge

Forge combines the general execution runtime and the Codex capability:

- shell and Python execution;
- project toolchains and compilation;
- Git and GitHub CLI;
- Codex CLI;
- image inspection, generation, and editing;
- file inspection and artifact handling.

Jobs run as the non-root `forge` user. The SSH daemon may start with the
privileges required to initialize the service, but authorized commands are
executed as `forge`.

Forge has direct internet access for Codex, GitHub, package repositories, and
dependency downloads. It receives no Recon credentials and no Docker socket.

### Recon

Recon contains network-specific tooling and runs jobs as the non-root `recon`
user. Direct internet access is the default route. Tor is used only when the
caller explicitly selects the Tor capability, such as when an authorized
request is blocked or rate-limited.

Recon records `route=direct` or `route=tor` in every result. A Tor failure never
falls back silently to the direct route.

## Naming

Operational names:

```text
Services:       hermes, forge, recon
Images:         ghcr.io/uphiago/barbarossa-forge
                ghcr.io/uphiago/barbarossa-recon
MCP server:     barbarossa
Users:          hermes, forge, recon
Environment:    BARBAROSSA_*
Jobs:           job_<type>_<id>
Job workspace:  /workspace/jobs/<job-id>/
```

Logical capabilities keep functional names:

```text
code.delegate
runtime.execute
media.file.inspect
media.image.inspect
media.image.generate
media.image.edit
network.inspect
network.fetch
network.tor
```

MCP tool identifiers use underscore-separated equivalents where required by
the tool protocol.

## Codex Configuration

Codex is a Forge capability, not the orchestrator:

```toml
model = "gpt-5.6"
model_reasoning_effort = "medium"

[features]
multi_agent = true

[agents]
max_concurrent_threads_per_session = 1

[tools]
view_image = true
```

`max_concurrent_threads_per_session = 1` permits the primary Codex thread plus
one spawned subagent, for a maximum of two Codex threads in the active Codex
job.

The Forge router starts only one top-level Codex job at a time. It invokes
Codex non-interactively, supplies an isolated working directory, and captures
structured output and the final response.

Image capabilities map as follows:

```text
media.image.inspect  -> codex exec --image <path> ...
media.image.generate -> codex exec '$imagegen ...'
media.image.edit     -> codex exec --image <reference> '$imagegen ...'
```

The deployment verifies that the official `$imagegen` skill is available.
Built-in generation uses the account's Codex image-generation allowance. An
`OPENAI_API_KEY` may be injected later for separately billed API generation,
but it is not required for the initial deployment and is never built into an
image.

## Capability Routing

Hermes agents call fixed MCP tools instead of choosing SSH hosts or assembling
remote shell commands themselves. The router maps each request to exactly one
worker and capability.

```text
Hermes child A -> runtime.execute     -> Forge runtime lane
Hermes child B -> code.delegate      -> Forge Codex lane
Hermes child C -> network.inspect    -> Recon lane
```

Router job tools:

```text
job.start
job.status
job.logs
job.submit
job.cancel
job.result
```

`job.start` validates the capability, input paths, limits, and requested route,
then returns a job identifier. Subsequent operations reference that identifier;
they never accept an arbitrary worker address.

## Concurrency And Resources

Hermes may run up to three delegated children. Router admission limits are:

```text
Forge runtime lane:  1 active job
Forge Codex lane:    1 active job
Recon lane:          1 active job
```

The two Forge lanes may run concurrently. Image inspection and generation use
the Codex lane. Excess work remains queued instead of creating more processes.

Default execution timeouts:

```text
Codex:   45 minutes
Runtime: 15 minutes
Recon:   20 minutes
Images:  20 minutes
```

Callers may request a larger timeout up to a configured maximum. On timeout,
the router attempts controlled termination before issuing `SIGKILL`.

Initial container limits for the two-vCPU, approximately 4 GiB OVH host are:

```text
hermes:  768 MiB, 256 PIDs
forge:   1408 MiB, 384 PIDs
recon:   640 MiB, 256 PIDs
```

CPU is scheduled using relative weights, with Forge receiving the largest
share. The design leaves approximately 1 GiB of RAM outside container limits
for the host, Docker, and transient overhead.

## Job State And Artifacts

Jobs use this state model:

```text
queued -> running -> succeeded | failed | cancelled | interrupted
```

Each workspace has a stable layout:

```text
/workspace/jobs/<job-id>/
|-- inputs/
|-- outputs/
|-- stdout.log
|-- stderr.log
`-- result.json
```

`result.json` includes at least:

- `job_id`
- `capability`
- `worker`
- `route`
- `status`
- `started_at`
- `finished_at`
- `exit_code`
- `artifacts`
- `error`

There is no time-based cleanup. Jobs and artifacts remain until explicitly
removed or until the relevant volume or stack is destroyed. This state is
convenient but not durable. The operator or an authorized agent manually
promotes valuable files, skills, and configuration to the selected private Git
repository.

## Persistent And Disposable State

The deployment uses local named volumes:

```text
hermes-state
forge-workspace
forge-codex-home
recon-workspace
```

Named volumes survive ordinary container recreation on the same host. They are
not backed up or migrated automatically and may be discarded during relocation.

Version-controlled configuration is mounted read-only where possible. Codex
authentication and sessions live under `forge-codex-home`; the deployment
bootstraps or reauthorizes them when starting on a new host.

## Secrets And SSH Control

Secrets are provided by GitHub Actions or the deployment environment and never
stored in Git, Docker build layers, or generated logs.

Relevant secret classes include:

- Hermes model-provider credentials;
- Telegram/API credentials;
- Codex authentication;
- optional repository-scoped GitHub credentials;
- the deployment-time worker control key.

The worker control key is ephemeral and replaceable. Deployment generates the
key, installs only the required public key on each worker, and supplies the
private key only to the router. Worker host keys are pinned in a generated
`known_hosts`; strict host-key checking remains enabled.

Forge and Recon never receive each other's SSH keys. Environment variables
passed to jobs use an allowlist. Log handling redacts authorization headers,
private keys, access tokens, and known secret values.

## Filesystem And Input Safety

Every job is restricted to its own workspace. Router input handling:

- rejects path traversal and symlink escapes;
- validates file type and size before staging;
- applies capability-specific input count and size limits;
- bounds captured output and log size;
- never treats caller-provided paths as shell fragments.

Workers receive no host filesystem mounts beyond their intended configuration
and named volumes.

## Repository Layout

```text
barbarossa/
|-- docker-compose.yml
|-- containers/
|   |-- forge/
|   |   `-- Dockerfile
|   |-- recon/
|   |   `-- Dockerfile
|   `-- shared/
|-- router/
|   |-- src/barbarossa_router/
|   |-- tests/
|   `-- locked dependency metadata
|-- config/
|   |-- codex/config.toml
|   `-- hermes/
|-- skills/
|   |-- hermes/
|   |   |-- barbarossa-routing/
|   |   |-- barbarossa-codex/
|   |   `-- barbarossa-network/
|   `-- codex/
|-- ops/host/
|-- tests/
`-- docs/
```

`containers/` replaces `workers/charlie`, `workers/oscar`, and
`workers/papa`. The name avoids confusing container build definitions with
generated media.

The public Barbarossa repository contains only reusable infrastructure,
documentation, safe defaults, and public skills. Promoted private artifacts and
private skills remain in the separate private repository.

## Failure Handling

- SSH unavailable: fail the affected job without rerouting it.
- Queue full: retain the job as queued or return an explicit capacity error.
- Worker restart: mark active jobs `interrupted` after reconciliation.
- Router restart: reconstruct terminal state from job workspaces where
  possible; running processes without reliable identity become `interrupted`.
- Codex or image-generation failure: retain logs, exit status, and partial
  artifacts.
- Invalid result: fail schema validation even when the process exits with zero.
- Tor failure: return an error without direct-network fallback.
- Router unavailable: keep Hermes running while Barbarossa capabilities report
  unavailable.

No error path may expose a secret or silently weaken the selected isolation or
network route.

## Direct Cutover

The old deployment contains no state that needs migration. Replacement is
direct:

1. CI validates configuration, tests the router, scans for secrets, builds
   Forge and Recon, and publishes immutable image tags.
2. Deployment confirms required secrets, host disk capacity, firewall state,
   and host SSH access.
3. Stop Hermes, Charlie, Oscar, and Papa.
4. Remove their containers and obsolete volumes.
5. Pull the new images and start Hermes, Forge, and Recon.
6. Run remote security and capability smoke tests.

The new Telegram consumer starts only after the old Hermes is stopped. There is
no data rollback. Redeploying a previous Git revision is the configuration
rollback strategy.

## Verification

CI and local tests cover:

- router request validation and result schemas;
- queue and timeout behavior;
- path traversal and symlink rejection;
- secret redaction;
- capability-to-worker routing;
- Compose configuration;
- container healthchecks;
- image build and secret scanning.

Post-deploy smoke tests verify:

1. Hermes responds and connects to Telegram.
2. The router publishes all expected capabilities.
3. `runtime.execute` completes in Forge.
4. Codex completes a basic task.
5. Codex successfully creates one subagent.
6. Codex inspects an input image.
7. Codex generates an output image.
8. Recon reaches the internet directly.
9. Recon reaches the internet through explicit Tor routing.
10. Forge and Recon cannot connect to each other.
11. Workers cannot access the Docker socket or unintended host paths.
12. Secrets do not appear in container or job logs.

The deployment workflow fails when an essential capability or an isolation
check fails.

## Acceptance Criteria

- Only Hermes, Forge, and Recon remain as long-running application containers.
- DeepSeek V4 Flash powers Hermes and its native subagents.
- Codex runs only within Forge using GPT-5.6 with medium reasoning.
- Codex supports one internal subagent and image inspection/generation/editing.
- Hermes can run Forge runtime, Forge Codex, and Recon work concurrently within
  the defined admission limits.
- Forge and Recon remain mutually isolated and expose no host ports.
- Direct and Tor network routes are explicit and auditable.
- Rebuilding on a new host requires no worker-state migration.
- No secret is committed, baked into images, or emitted into logs.
- Job workspaces have no automatic time-based deletion.

## References

- [Hermes delegation](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation)
- [Hermes MCP integration](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp/)
- [Hermes Codex skill](https://hermes-agent.nousresearch.com/docs/user-guide/skills/bundled/autonomous-ai-agents/autonomous-ai-agents-codex)
- [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
- [Codex advanced configuration](https://learn.chatgpt.com/docs/config-file/config-advanced)
- [Codex image inputs](https://learn.chatgpt.com/docs/image-inputs)
- [Codex image generation](https://learn.chatgpt.com/docs/image-generation)
