# Barbarossa Worker Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Charlie, Oscar, and Papa with a disposable Hermes, Forge, and Recon stack whose typed MCP router safely dispatches runtime, Codex, image, direct-network, and Tor jobs.

**Architecture:** Hermes runs the `barbarossa-router` MCP v2 server over stdio and reaches Forge and Recon through distinct SSH control networks. The router persists its queue in SQLite, enforces one runtime, one Codex, and one Recon lane, and calls a restricted worker RPC instead of exposing arbitrary SSH. Forge hosts Codex and general toolchains; Recon hosts network tooling and optional Tor.

**Tech Stack:** Docker Compose, Python 3.12, MCP Python SDK 2.0.0, Pydantic 2.13.4, AsyncSSH 2.24.0, SQLite, pytest 9.1.1, PEX 2.98.4, Bash, OpenSSH, Codex CLI 0.145.0, GitHub Actions.

---

## Compatibility Decision

Use MCP Python SDK `2.0.0`, the stable v2 release, rather than the maintained
v1 line. Implement the high-level server with `MCPServer`, return Pydantic
models for structured output, and test with the v2 in-memory `Client(mcp)`.
Hermes may still negotiate the older MCP protocol; the v2 SDK serves current
and legacy clients from the same stdio server.

References:

- <https://py.sdk.modelcontextprotocol.io/whats-new/>
- <https://py.sdk.modelcontextprotocol.io/get-started/testing/>
- <https://py.sdk.modelcontextprotocol.io/servers/tools/>
- <https://py.sdk.modelcontextprotocol.io/servers/structured-output/>
- <https://py.sdk.modelcontextprotocol.io/servers/handling-errors/>

## File Map

Create:

```text
router/
├── pyproject.toml
├── uv.lock
├── Containerfile.bundle
├── src/barbarossa_router/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── models.py
│   ├── redaction.py
│   ├── scheduler.py
│   ├── server.py
│   ├── ssh.py
│   └── store.py
└── tests/
    ├── conftest.py
    ├── test_models.py
    ├── test_redaction.py
    ├── test_scheduler.py
    ├── test_packaged_server.py
    ├── test_server.py
    ├── test_ssh.py
    └── test_store.py

containers/
├── shared/
│   ├── worker-entrypoint.sh
│   ├── worker-rpc.py
│   └── worker-ssh-dispatch.sh
├── forge/
│   └── Dockerfile
└── recon/
    ├── Dockerfile
    └── tor-entrypoint.sh

config/
├── codex/config.toml
└── hermes/configure.py

skills/
├── hermes/
│   ├── barbarossa-routing/SKILL.md
│   ├── barbarossa-codex/SKILL.md
│   └── barbarossa-network/SKILL.md
└── codex/
    └── barbarossa-artifacts/SKILL.md

scripts/
├── deploy-runtime-files.sh
└── smoke-remote.sh

tests/
├── container-integration.sh
└── fixtures/tiny.png
```

Modify:

```text
.dockerignore
.env.example
.github/workflows/build-deploy.yml
.gitignore
AGENTS.md
README.md
WORKERS.md
docker-compose.yml
setup.sh
tests/infra-regression.sh
```

Delete after replacement tests pass:

```text
workers/charlie/
workers/oscar/
workers/papa/
workers/shared/
```

## Task 1: Router Package And Typed Contracts

**Files:**
- Create: `router/pyproject.toml`
- Create: `router/src/barbarossa_router/__init__.py`
- Create: `router/src/barbarossa_router/config.py`
- Create: `router/src/barbarossa_router/models.py`
- Create: `router/src/barbarossa_router/redaction.py`
- Create: `router/tests/conftest.py`
- Create: `router/tests/test_models.py`
- Create: `router/tests/test_redaction.py`

- [ ] **Step 1: Add failing contract tests**

```python
# router/tests/test_models.py
import pytest
from pydantic import ValidationError

from barbarossa_router.models import JobRequest, JobStatus


def test_codex_request_uses_codex_lane() -> None:
    request = JobRequest(capability="code.delegate", prompt="Review this repo")
    assert request.worker == "forge"
    assert request.lane == "codex"
    assert request.route == "direct"
    assert request.timeout_seconds == 2700


def test_tor_is_valid_only_for_network_capabilities() -> None:
    with pytest.raises(ValidationError):
        JobRequest(
            capability="runtime.execute",
            command="printf ok",
            route="tor",
        )


def test_job_status_has_stable_machine_fields() -> None:
    status = JobStatus(
        job_id="job_runtime_01J00000000000000000000000",
        capability="runtime.execute",
        worker="forge",
        lane="runtime",
        route="direct",
        status="queued",
    )
    assert status.model_dump()["exit_code"] is None
```

```python
# router/tests/test_redaction.py
from barbarossa_router.redaction import Redactor


def test_redacts_known_secret_and_authorization_header() -> None:
    redactor = Redactor(["super-secret-value"])
    text = "Authorization: Bearer abc123 super-secret-value"
    assert redactor.clean(text) == "Authorization: [REDACTED] [REDACTED]"
```

- [ ] **Step 2: Run the tests and verify the missing package failure**

Run:

```bash
cd router
uv run --with pytest==9.1.1 pytest tests/test_models.py tests/test_redaction.py -q
```

Expected: collection fails with `ModuleNotFoundError: barbarossa_router`.

- [ ] **Step 3: Add the locked project definition**

```toml
# router/pyproject.toml
[build-system]
requires = ["hatchling==1.28.0"]
build-backend = "hatchling.build"

[project]
name = "barbarossa-router"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "asyncssh==2.24.0",
  "mcp==2.0.0",
  "pydantic==2.13.4",
]

[project.scripts]
barbarossa-router = "barbarossa_router.cli:main"

[dependency-groups]
dev = [
  "pytest==9.1.1",
  "pytest-asyncio==1.4.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

Run:

```bash
cd router
uv lock
uv sync --frozen
```

Expected: `uv.lock` is created and all dependencies install without a
pre-release.

- [ ] **Step 4: Implement capability and result models**

Define these exact public types in `models.py`:

```python
from datetime import datetime, timezone
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator

Capability = Literal[
    "runtime.execute",
    "code.delegate",
    "media.file.inspect",
    "media.image.inspect",
    "media.image.generate",
    "media.image.edit",
    "network.inspect",
    "network.fetch",
    "network.tor",
]
JobState = Literal[
    "queued", "running", "succeeded", "failed", "cancelled", "interrupted"
]
Route = Literal["direct", "tor"]

CAPABILITY_POLICY = {
    "runtime.execute": ("forge", "runtime", 900),
    "code.delegate": ("forge", "codex", 2700),
    "media.file.inspect": ("forge", "runtime", 900),
    "media.image.inspect": ("forge", "codex", 1200),
    "media.image.generate": ("forge", "codex", 1200),
    "media.image.edit": ("forge", "codex", 1200),
    "network.inspect": ("recon", "recon", 1200),
    "network.fetch": ("recon", "recon", 1200),
    "network.tor": ("recon", "recon", 1200),
}


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: Capability
    command: str | None = Field(default=None, max_length=32_768)
    prompt: str | None = Field(default=None, max_length=65_536)
    url: AnyHttpUrl | None = None
    route: Route = "direct"
    timeout_seconds: int | None = Field(default=None, ge=1, le=7200)
    input_paths: list[str] = Field(default_factory=list, max_length=8)

    worker: Literal["forge", "recon"] = "forge"
    lane: Literal["runtime", "codex", "recon"] = "runtime"

    @model_validator(mode="after")
    def apply_policy(self) -> "JobRequest":
        worker, lane, default_timeout = CAPABILITY_POLICY[self.capability]
        self.worker = worker
        self.lane = lane
        self.timeout_seconds = self.timeout_seconds or default_timeout
        if self.capability == "network.tor":
            self.route = "tor"
        elif self.route == "tor":
            raise ValueError("Tor route requires network.tor")
        if self.capability in {"runtime.execute", "network.inspect"} and not self.command:
            raise ValueError("command is required for this capability")
        if self.capability.startswith(("code.", "media.image.")) and not self.prompt:
            raise ValueError("prompt is required for this capability")
        if self.capability == "network.fetch" and self.url is None:
            raise ValueError("url is required for network.fetch")
        if self.capability in {"media.file.inspect", "media.image.inspect", "media.image.edit"}:
            if len(self.input_paths) != 1:
                raise ValueError("this capability requires exactly one input file")
        if self.capability == "media.image.generate" and self.input_paths:
            raise ValueError("media.image.generate does not accept an input file")
        return self


class JobStatus(BaseModel):
    job_id: str = Field(
        pattern=r"^job_(runtime|codex|image|recon)_[0-9A-HJKMNP-TV-Z]{26}$"
    )
    capability: Capability
    worker: Literal["forge", "recon"]
    lane: Literal["runtime", "codex", "recon"]
    route: Route
    status: JobState
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    exit_code: int | None = None
    artifacts: list[str] = Field(default_factory=list)
    error: str | None = None
```

`config.py` must load only `BARBAROSSA_*` values and validate that the SSH key,
known-hosts file, state database, input root, and result root are absolute
paths. The input root is `/opt/data/barbarossa-transfer`; the result root is
`/opt/data/barbarossa-results`. Neither may contain the SSH or router state
directories.

- [ ] **Step 5: Implement bounded redaction**

`Redactor.clean()` must replace known secret values, bearer/basic
authorization headers, OpenAI-style keys, GitHub tokens, and PEM blocks. It
must truncate cleaned output at `BARBAROSSA_MAX_LOG_BYTES`, defaulting to
`200_000`.

```python
import re

AUTH_HEADER_RE = re.compile(
    r"(?im)^(authorization:\s*)(?:bearer|basic)\s+\S+"
)
TOKEN_RE = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{16,})\b"
)
PEM_RE = re.compile(
    r"-----BEGIN [^-]*PRIVATE KEY-----.*?"
    r"-----END [^-]*PRIVATE KEY-----",
    re.DOTALL,
)


class Redactor:
    def __init__(self, secrets: list[str], max_bytes: int = 200_000) -> None:
        self._secrets = sorted((s for s in secrets if s), key=len, reverse=True)
        self._max_bytes = max_bytes

    def clean(self, value: str) -> str:
        cleaned = AUTH_HEADER_RE.sub(r"\1[REDACTED]", value)
        cleaned = TOKEN_RE.sub("[REDACTED]", cleaned)
        cleaned = PEM_RE.sub("[REDACTED PRIVATE KEY]", cleaned)
        for secret in self._secrets:
            cleaned = cleaned.replace(secret, "[REDACTED]")
        return cleaned.encode()[: self._max_bytes].decode(errors="replace")
```

- [ ] **Step 6: Run the unit tests**

Run:

```bash
cd router
uv run pytest tests/test_models.py tests/test_redaction.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add router
git commit -m "feat: define barbarossa router contracts"
```

## Task 2: Durable Queue And Lane Scheduler

**Files:**
- Create: `router/src/barbarossa_router/store.py`
- Create: `router/src/barbarossa_router/scheduler.py`
- Create: `router/tests/test_store.py`
- Create: `router/tests/test_scheduler.py`

- [ ] **Step 1: Write failing SQLite and concurrency tests**

```python
# router/tests/test_store.py
async def test_store_round_trips_queued_job(store, runtime_request):
    created = await store.create(runtime_request)
    loaded = await store.get(created.job_id)
    assert loaded == created
    assert await store.next_queued("runtime") == created


async def test_store_lists_running_jobs_for_remote_reconciliation(
    store, runtime_request
):
    created = await store.create(runtime_request)
    await store.mark_running(created.job_id, remote_pid=42)
    assert await store.list_running() == [await store.get(created.job_id)]
```

```python
# router/tests/test_scheduler.py
async def test_one_job_per_lane_and_runtime_parallel_with_codex(
    scheduler, fake_transport, runtime_request, codex_request
):
    await scheduler.submit(runtime_request)
    await scheduler.submit(runtime_request)
    await scheduler.submit(codex_request)
    await scheduler.tick()
    assert fake_transport.started_lanes == ["runtime", "codex"]


async def test_reconcile_keeps_confirmed_remote_process_running(
    scheduler, fake_transport, running_job
):
    fake_transport.statuses[running_job.job_id] = {"status": "running"}
    await scheduler.reconcile()
    assert (await scheduler.store.get(running_job.job_id)).status == "running"
```

- [ ] **Step 2: Verify the tests fail**

Run:

```bash
cd router
uv run pytest tests/test_store.py tests/test_scheduler.py -q
```

Expected: imports for `store` and `scheduler` fail.

- [ ] **Step 3: Implement the SQLite store**

Use `sqlite3` with `PRAGMA journal_mode=WAL`, one process-local
`asyncio.Lock`, and `asyncio.to_thread()` around database work. Create a
`jobs` table with the `JobStatus` fields plus `request_json`, `remote_pid`, and
monotonic `queue_position`.

The public API contains `initialize()`, `create(request)`, `get(job_id)`,
`next_queued(lane)`, `mark_running(job_id, remote_pid)`,
`finish(job_id, status, exit_code, artifacts, error)`, and
`list_running()`. `create`, `get`, `mark_running`, and `finish` return
`JobStatus`; `next_queued` returns `JobStatus | None`, and `list_running`
returns `list[JobStatus]`.

Generate IDs with a capability prefix and 26 uppercase Crockford characters,
for example `job_runtime_01J00000000000000000000000`. Reject lookups that do
not match:

```python
JOB_ID_RE = re.compile(r"^job_(runtime|codex|image|recon)_[0-9A-HJKMNP-TV-Z]{26}$")
```

- [ ] **Step 4: Implement lane admission**

`Scheduler` owns three `asyncio.Semaphore(1)` objects keyed by `runtime`,
`codex`, and `recon`. `submit()` persists before scheduling. `tick()` starts
at most one queued job per free lane. A background task polls running jobs
every two seconds and releases the lane only after a terminal worker result.

At startup, `reconcile()` queries the assigned worker for every persisted
running job. It reserves the matching lane when the worker confirms the
process, copies a terminal remote result into SQLite, and marks the job
`interrupted` only when the worker cannot confirm the job identity.

Cancellation must call the transport first and then persist `cancelled`; it
must not mark a job cancelled when the worker rejects the cancellation.

- [ ] **Step 5: Run store and scheduler tests**

Run:

```bash
cd router
uv run pytest tests/test_store.py tests/test_scheduler.py -q
```

Expected: all tests pass, including FIFO ordering and lane isolation.

- [ ] **Step 6: Commit**

```bash
git add router/src/barbarossa_router/store.py \
  router/src/barbarossa_router/scheduler.py \
  router/tests/test_store.py router/tests/test_scheduler.py
git commit -m "feat: add durable worker job scheduling"
```

## Task 3: Restricted SSH Transport

**Files:**
- Create: `router/src/barbarossa_router/ssh.py`
- Create: `router/tests/test_ssh.py`

- [ ] **Step 1: Write failing transport tests**

Test that:

- Forge always uses host `forge`, user `forge`, and the pinned known-hosts file.
- Recon always uses host `recon`, user `recon`.
- RPC requests use the fixed remote command `barbarossa-worker rpc`.
- Job IDs and archive entry names are rejected before upload when unsafe.
- Neither command strings nor prompts become part of the SSH command line.

```python
async def test_payload_is_sent_on_stdin(fake_asyncssh, ssh_transport):
    await ssh_transport.rpc("forge", {"action": "status", "job_id": SAFE_JOB_ID})
    call = fake_asyncssh.calls[0]
    assert call.command == "barbarossa-worker rpc"
    assert json.loads(call.input)["job_id"] == SAFE_JOB_ID
```

- [ ] **Step 2: Verify the tests fail**

Run:

```bash
cd router
uv run pytest tests/test_ssh.py -q
```

Expected: `barbarossa_router.ssh` cannot be imported.

- [ ] **Step 3: Implement AsyncSSH connections**

Create one lazily initialized connection per worker with:

```python
await asyncssh.connect(
    host=worker.host,
    port=22,
    username=worker.user,
    client_keys=[settings.ssh_key],
    known_hosts=settings.known_hosts,
    agent_path=None,
    connect_timeout=10,
    keepalive_interval=30,
    keepalive_count_max=3,
)
```

`rpc()` serializes JSON and sends it on stdin to the fixed command. Treat
non-zero SSH exit status, malformed JSON, response bodies over 1 MiB, and a
worker name outside `forge|recon` as explicit transport errors.

For uploads, create an in-memory tar stream containing only regular files with
sanitized basenames. Resolve every caller path with `Path.resolve(strict=True)`
and require it to be a descendant of `BARBAROSSA_INPUT_ROOT` before opening it.
Then call:

```text
barbarossa-worker upload job_image_01J00000000000000000000000
```

For artifact download, call:

```text
barbarossa-worker download job_image_01J00000000000000000000000
```

Reject device files, links, absolute tar members, `..`, and archives over the
configured input/output limits.

- [ ] **Step 4: Run transport tests**

Run:

```bash
cd router
uv run pytest tests/test_ssh.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add router/src/barbarossa_router/ssh.py router/tests/test_ssh.py
git commit -m "feat: add restricted worker ssh transport"
```

## Task 4: Worker RPC And Process Supervision

**Files:**
- Create: `containers/shared/worker-rpc.py`
- Create: `containers/shared/worker-ssh-dispatch.sh`
- Create: `containers/shared/worker-entrypoint.sh`
- Create: `tests/test-worker-rpc.py`

- [ ] **Step 1: Write failing worker protocol tests**

Load `worker-rpc.py` with `importlib.util.spec_from_file_location()` and test:

```python
def test_workspace_rejects_traversal(worker_rpc, tmp_path):
    with pytest.raises(ValueError, match="invalid job id"):
        worker_rpc.workspace(tmp_path, "../../root")


def test_runtime_environment_contains_no_secret(worker_rpc):
    env = worker_rpc.job_environment("runtime.execute", {})
    assert set(env) == {"HOME", "LANG", "PATH", "TZ"}


def test_codex_argv_is_not_shell_interpolated(worker_rpc, safe_job):
    argv = worker_rpc.build_argv(
        safe_job,
        {"capability": "code.delegate", "prompt": "review; touch /tmp/pwned"},
    )
    assert argv[0:2] == ["codex", "exec"]
    assert argv[-1] == "review; touch /tmp/pwned"
```

- [ ] **Step 2: Verify the tests fail**

Run:

```bash
uv run --with pytest==9.1.1 pytest tests/test-worker-rpc.py -q
```

Expected: the worker RPC file does not exist.

- [ ] **Step 3: Implement the forced-command dispatcher**

`worker-ssh-dispatch.sh` accepts exactly:

```bash
case "${SSH_ORIGINAL_COMMAND:-}" in
  "barbarossa-worker rpc")
    exec /usr/local/bin/barbarossa-worker rpc
    ;;
  barbarossa-worker\ upload\ job_*)
    exec /usr/local/bin/barbarossa-worker upload \
      "${SSH_ORIGINAL_COMMAND##* }"
    ;;
  barbarossa-worker\ download\ job_*)
    exec /usr/local/bin/barbarossa-worker download \
      "${SSH_ORIGINAL_COMMAND##* }"
    ;;
  *)
    printf 'command denied\n' >&2
    exit 126
    ;;
esac
```

The Python command must revalidate every argument; the shell pattern is not the
security boundary.

- [ ] **Step 4: Implement worker lifecycle operations**

`worker-rpc.py` supports `start`, `status`, `logs`, `cancel`, and `result`.
It creates:

```text
/workspace/jobs/{job_id}/
├── inputs/
├── outputs/
├── request.json
├── status.json
├── stdout.log
├── stderr.log
└── result.json
```

The `start` RPC writes `request.json`, then starts a detached copy of the
worker as the job supervisor:

```python
supervisor = subprocess.Popen(
    [sys.executable, __file__, "run-job", job_id],
    cwd=workspace,
    env={"HOME": worker_home, "LANG": "C.UTF-8", "PATH": SAFE_PATH},
    stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    start_new_session=True,
)
```

`run-job` acquires the lane lock, keeps its file descriptor open for the
lifetime of the job, launches the capability argv with stdout and stderr
redirected to the workspace, waits for it, and atomically writes the terminal
`result.json`. The capability child does not inherit the lock descriptor; the
supervisor owns admission until it has recorded the final result. The SSH RPC
exit and router restarts therefore cannot release admission early.

Persist the supervisor PID and process start time atomically. Cancellation
sends `SIGTERM` to the supervisor process group, waits ten seconds, then sends
`SIGKILL`. Status reconciliation checks both PID and
`/proc/{pid}/stat` start time so a reused PID cannot be killed. The supervisor
traps termination, records `cancelled`, and preserves partial artifacts.

Use lane lock files under `/workspace/.locks/`. `flock(LOCK_EX | LOCK_NB)`
must reject a second active process in the same lane even if the router is
restarted.

- [ ] **Step 5: Implement safe upload and download**

Upload extraction permits regular files only, enforces 32 MiB total input and
eight members, and writes into `inputs/`. Download creates a tar containing
only `outputs/`, redacted logs, and `result.json`, capped at 64 MiB.

- [ ] **Step 6: Implement the generic worker entrypoint**

The entrypoint:

1. validates `WORKER_USER`;
2. generates one Ed25519 host key in `/ssh-host-keys` when absent;
3. copies the mounted restricted authorized-keys file into the worker user's
   home with mode `0600`;
4. creates `/workspace/jobs` and `/workspace/.locks`;
5. drops ownership to the worker user for all job paths;
6. executes the service command.

- [ ] **Step 7: Run worker tests**

Run:

```bash
uv run --with pytest==9.1.1 pytest tests/test-worker-rpc.py -q
```

Expected: all worker validation, environment, process, and archive tests pass.

- [ ] **Step 8: Commit**

```bash
git add containers/shared tests/test-worker-rpc.py
git commit -m "feat: add restricted worker rpc"
```

## Task 5: MCP v2 Server And Router CLI

**Files:**
- Create: `router/src/barbarossa_router/server.py`
- Create: `router/src/barbarossa_router/cli.py`
- Create: `router/tests/test_server.py`

- [ ] **Step 1: Write failing in-memory MCP tests**

Use the SDK v2 testing pattern:

```python
import pytest
from mcp import Client

from barbarossa_router.server import create_server


@pytest.fixture
async def client(fake_service):
    server = create_server(fake_service)
    async with Client(server, raise_exceptions=True) as connected:
        yield connected


async def test_runtime_execute_returns_structured_job(client):
    result = await client.call_tool(
        "runtime_execute",
        {"command": "printf ok", "timeout_seconds": 30},
    )
    assert result.is_error is False
    assert result.structured_content["status"] == "queued"
    assert result.structured_content["worker"] == "forge"


async def test_invalid_route_is_a_model_visible_tool_error(client):
    result = await client.call_tool(
        "network_tor",
        {"command": "", "timeout_seconds": 30},
    )
    assert result.is_error is True
```

- [ ] **Step 2: Verify the tests fail**

Run:

```bash
cd router
uv run pytest tests/test_server.py -q
```

Expected: `create_server` cannot be imported.

- [ ] **Step 3: Register the MCP v2 tools**

Build the server with:

```python
from contextlib import asynccontextmanager

from mcp.server import MCPServer


def create_server(service: RouterService) -> MCPServer:
    @asynccontextmanager
    async def lifespan(_: MCPServer):
        await service.start()
        try:
            yield None
        finally:
            await service.close()

    mcp = MCPServer(
        "barbarossa",
        version="1.0.0",
        instructions=(
            "Dispatch jobs to Forge or Recon. Start a job, then use status, "
            "logs, result, or cancel with the returned job_id."
        ),
        lifespan=lifespan,
    )

    @mcp.tool()
    async def runtime_execute(
        command: str, timeout_seconds: int = 900
    ) -> JobStatus:
        """Queue an isolated shell job in the Forge runtime lane."""
        return await service.submit(JobRequest(
            capability="runtime.execute",
            command=command,
            timeout_seconds=timeout_seconds,
        ))

    return mcp
```

Register typed tools for:

```text
runtime_execute
code_delegate
media_file_inspect
media_image_inspect
media_image_generate
media_image_edit
network_inspect
network_fetch
network_tor
job_status
job_logs
job_cancel
job_result
```

Return `JobStatus` or a dedicated Pydantic response model from every tool.
`job_result` downloads the bounded worker archive, safely extracts it under
`/opt/data/barbarossa-results/{job_id}`, and returns only paths beneath that
directory. Repeated calls are idempotent and replace files only inside the same
job result directory.
Raise ordinary `ValueError` for correctable input or capacity errors so MCP v2
returns `is_error=True`. Do not return error strings as successful results.
Reserve stdout exclusively for MCP framing; configure application logging to
stderr and forbid `print()` in the server, scheduler, store, and SSH transport.

- [ ] **Step 4: Add CLI commands**

`barbarossa-router serve` starts `mcp.run(transport="stdio")`.
`barbarossa-router health` verifies the database and both SSH workers.
`barbarossa-router submit --capability runtime.execute --command 'printf ok'
--wait` is a deterministic operator path for smoke tests.

```python
def main() -> None:
    args = parser().parse_args()
    if args.command == "serve":
        create_server(build_service()).run(transport="stdio")
    else:
        raise SystemExit(asyncio.run(run_operator_command(args)))
```

- [ ] **Step 5: Run all router tests**

Run:

```bash
cd router
uv run pytest -q
```

Expected: all tests pass; server tests negotiate MCP in memory without a
subprocess or network port.

- [ ] **Step 6: Commit**

```bash
git add router/src/barbarossa_router/server.py \
  router/src/barbarossa_router/cli.py router/tests/test_server.py
git commit -m "feat: expose worker jobs through mcp v2"
```

## Task 6: Forge Image And Codex Capabilities

**Files:**
- Create: `containers/forge/Dockerfile`
- Create: `config/codex/config.toml`
- Create: `skills/codex/barbarossa-artifacts/SKILL.md`
- Test: `tests/container-integration.sh`

- [ ] **Step 1: Add failing Forge image assertions**

Add assertions that build Forge and verify:

```bash
docker run --rm barbarossa-forge:test codex --version |
  grep -F 'codex-cli 0.145.0'
docker run --rm barbarossa-forge:test id -u forge | grep -Fx '10001'
docker run --rm barbarossa-forge:test test ! -S /var/run/docker.sock
docker run --rm barbarossa-forge:test python3 \
  /usr/local/bin/barbarossa-worker self-test
```

- [ ] **Step 2: Verify the Forge build test fails**

Run:

```bash
bash tests/container-integration.sh forge
```

Expected: failure because `containers/forge/Dockerfile` is absent.

- [ ] **Step 3: Build the Forge image**

Use:

```dockerfile
FROM node:24-bookworm-slim@sha256:6f7b03f7c2c8e2e784dcf9295400527b9b1270fd37b7e9a7285cf83b6951452d

ARG CODEX_VERSION=0.145.0

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates curl file git gh jq openssh-server \
    python3 python3-pip rsync tar unzip \
    build-essential cmake gdb strace ltrace xxd \
    && rm -rf /var/lib/apt/lists/*

RUN npm install --global "@openai/codex@${CODEX_VERSION}" \
    && npm cache clean --force

RUN useradd --create-home --uid 10001 --shell /bin/bash forge \
    && install -d -o forge -g forge /workspace/jobs /workspace/.locks \
       /home/forge/.codex /run/sshd /ssh-host-keys

COPY containers/shared/worker-rpc.py /usr/local/bin/barbarossa-worker
COPY containers/shared/worker-ssh-dispatch.sh /usr/local/bin/worker-ssh-dispatch
COPY containers/shared/worker-entrypoint.sh /usr/local/bin/worker-entrypoint
RUN chmod 0755 /usr/local/bin/barbarossa-worker \
    /usr/local/bin/worker-ssh-dispatch /usr/local/bin/worker-entrypoint \
    && rm -f /etc/ssh/ssh_host_*

ENTRYPOINT ["/usr/local/bin/worker-entrypoint"]
CMD ["/usr/sbin/sshd", "-D", "-e", "-o", "PermitRootLogin=no", \
     "-o", "PasswordAuthentication=no", "-o", "PubkeyAuthentication=yes", \
     "-o", "AllowUsers=forge", \
     "-o", "ForceCommand=/usr/local/bin/worker-ssh-dispatch"]
```

- [ ] **Step 4: Add the Codex profile**

```toml
model = "gpt-5.6"
model_reasoning_effort = "medium"
approval_policy = "never"
sandbox_mode = "danger-full-access"
web_search = "live"

[features]
multi_agent = true

[agents]
max_concurrent_threads_per_session = 1

[tools]
view_image = true

[shell_environment_policy]
inherit = "none"
ignore_default_excludes = false
set = {
  PATH = "/usr/local/bin:/usr/bin:/bin",
  HOME = "/home/forge",
  CODEX_HOME = "/home/forge/.codex",
  GH_CONFIG_DIR = "/workspace/.config/gh",
  LANG = "C.UTF-8"
}
include_only = [
  "PATH", "HOME", "CODEX_HOME", "GH_CONFIG_DIR", "LANG"
]
```

`danger-full-access` is allowed only because Forge is the outer sandbox:
non-root user, constrained mounts, no Docker socket, isolated SSH interface,
memory/PID limits, and no host paths.

- [ ] **Step 5: Implement capability argv builders**

In `worker-rpc.py`, build argument lists without shell interpolation:

```python
if capability == "runtime.execute":
    return ["bash", "-lc", command]
if capability == "media.file.inspect":
    return ["file", "--brief", "--mime", "--", str(input_file)]
if capability == "code.delegate":
    return [
        "codex", "exec", "--json", "--output-last-message",
        str(workspace / "outputs" / "final.txt"),
        "--cd", str(workspace), prompt,
    ]
if capability == "media.image.inspect":
    return ["codex", "exec", "--image", str(image), "--cd", str(workspace), prompt]
if capability == "media.image.generate":
    image_prompt = (
        f"$imagegen {prompt}\n"
        f"Save generated files under {workspace / 'outputs'}."
    )
    return ["codex", "exec", "--cd", str(workspace), image_prompt]
if capability == "media.image.edit":
    edit_prompt = (
        f"$imagegen {prompt}\n"
        f"Save edited files under {workspace / 'outputs'}."
    )
    return [
        "codex", "exec", "--image", str(image), "--cd", str(workspace),
        edit_prompt,
    ]
```

The worker reads `/run/secrets/codex_access_token`, trims one final newline,
and sets `CODEX_ACCESS_TOKEN` only in Codex/image process environments.
Runtime jobs never receive it.

- [ ] **Step 6: Run Forge tests**

Run:

```bash
bash tests/container-integration.sh forge
```

Expected: the image builds, Codex reports `0.145.0`, the non-root account and
worker self-test pass, and no Docker socket exists.

- [ ] **Step 7: Commit**

```bash
git add containers/forge config/codex \
  skills/codex containers/shared/worker-rpc.py \
  tests/container-integration.sh
git commit -m "feat: build forge runtime with codex"
```

## Task 7: Recon Image With Explicit Tor Routing

**Files:**
- Create: `containers/recon/Dockerfile`
- Create: `containers/recon/tor-entrypoint.sh`
- Modify: `containers/shared/worker-rpc.py`
- Modify: `tests/container-integration.sh`

- [ ] **Step 1: Add failing Recon tests**

Test:

```bash
docker run --rm barbarossa-recon:test id -u recon | grep -Fx '10002'
docker run --rm barbarossa-recon:test sh -lc \
  'command -v nmap && command -v subfinder && command -v torsocks'
docker run --rm barbarossa-recon:test python3 \
  /usr/local/bin/barbarossa-worker self-test
```

Add a unit test proving `network.tor` wraps a command with `torsocks --isolate`
while `network.inspect` does not.

- [ ] **Step 2: Verify the Recon tests fail**

Run:

```bash
bash tests/container-integration.sh recon
uv run --with pytest==9.1.1 pytest tests/test-worker-rpc.py -q
```

Expected: Recon build and Tor routing tests fail.

- [ ] **Step 3: Build Recon**

Base Recon on:

```dockerfile
FROM alpine:3.22@sha256:14358309a308569c32bdc37e2e0e9694be33a9d99e68afb0f5ff33cc1f695dce
```

Install OpenSSH, Bash, Python, curl, jq, nmap, masscan, bind-tools, Tor,
torsocks, and the checksum-pinned ProjectDiscovery binaries currently used by
Charlie. Create user `recon` with UID `10002`, copy the shared RPC scripts, and
remove build-time SSH host keys.

Keep Tor bound only to `127.0.0.1:9050`. Do not expose SOCKS or SSH through a
Compose port.

- [ ] **Step 4: Supervise Tor and SSH**

`tor-entrypoint.sh` starts Tor, waits for the local SOCKS listener, starts
sshd, traps `INT` and `TERM`, and exits if either child exits. Preserve the
existing `wait -n` supervision behavior.

For `network.tor`, run:

```python
["torsocks", "--isolate", "bash", "-lc", command]
```

For `network.fetch`, do not accept a shell command. Validate an `https://` or
`http://` URL and use curl with:

```text
--fail-with-body --location --max-time "$TIMEOUT_SECONDS" --output outputs/body
--dump-header outputs/headers
```

- [ ] **Step 5: Run Recon tests**

Run:

```bash
bash tests/container-integration.sh recon
uv run --with pytest==9.1.1 pytest tests/test-worker-rpc.py -q
```

Expected: image, user, tooling, route-selection, and worker self-tests pass.

- [ ] **Step 6: Commit**

```bash
git add containers/recon containers/shared/worker-rpc.py \
  tests/container-integration.sh
git commit -m "feat: build isolated recon worker"
```

## Task 8: Compose, Hermes Bootstrap, And Skills

**Files:**
- Modify: `docker-compose.yml`
- Create: `config/hermes/configure.py`
- Create: `skills/hermes/barbarossa-routing/SKILL.md`
- Create: `skills/hermes/barbarossa-codex/SKILL.md`
- Create: `skills/hermes/barbarossa-network/SKILL.md`
- Modify: `AGENTS.md`
- Modify: `WORKERS.md`
- Modify: `.env.example`
- Modify: `.gitignore`
- Modify: `.dockerignore`

- [ ] **Step 1: Replace old regression expectations with failing new ones**

Update `tests/infra-regression.sh` to require:

- exactly `hermes`, `forge`, and `recon` services;
- no `container_name`;
- `hermes-forge` and `hermes-recon` networks;
- no network shared by Forge and Recon;
- no published Forge or Recon port;
- three healthchecks, memory limits, PID limits, and rotated logs;
- no Docker socket;
- required external worker key, authorized-keys, known-hosts, Codex token, and
  router bundle paths;
- pinned Hermes image digest;
- Forge at 1408 MiB, Hermes at 768 MiB, Recon at 640 MiB;
- separate worker host-key volumes;
- `mcp_servers.barbarossa` configuration with parallel calls enabled;
- no Charlie, Oscar, Papa, root worker login, or `StrictHostKeyChecking=no`.

- [ ] **Step 2: Run regression tests and verify failure**

Run:

```bash
bash tests/infra-regression.sh
```

Expected: failures identify the old service names, network, ports, worker
paths, and root SSH assumptions.

- [ ] **Step 3: Replace Compose**

Use the pinned Hermes image:

```text
nousresearch/hermes-agent@sha256:545ef5a71b52b63aab08e29721701681d64465594ae5ffe7e860a8a758da0371
```

Compose requirements:

```yaml
name: barbarossa

services:
  forge:
    image: ghcr.io/uphiago/barbarossa-forge:${BARBAROSSA_IMAGE_TAG:-latest}
    hostname: forge
    mem_limit: 1408m
    pids_limit: 384
    cpus: 1.50
    cpu_shares: 1024
    networks: [hermes-forge]

  recon:
    image: ghcr.io/uphiago/barbarossa-recon:${BARBAROSSA_IMAGE_TAG:-latest}
    hostname: recon
    mem_limit: 640m
    pids_limit: 256
    cpus: 1.00
    cpu_shares: 256
    networks: [hermes-recon]

  hermes:
    image: nousresearch/hermes-agent@sha256:545ef5a71b52b63aab08e29721701681d64465594ae5ffe7e860a8a758da0371
    hostname: hermes
    mem_limit: 768m
    pids_limit: 256
    cpus: 1.00
    cpu_shares: 512
    networks: [hermes-forge, hermes-recon]
```

All services use `no-new-privileges`, bounded `json-file` logs, and
healthchecks. Workers use read-only root filesystems where the integration
tests confirm it works, with explicit `tmpfs` mounts for `/tmp` and `/run`.

Mount:

```text
worker private key -> Hermes only, read-only
known_hosts        -> Hermes only, read-only
authorized_keys    -> both workers, read-only
Codex token        -> Forge only, read-only
router PEX         -> Hermes only, read-only
Codex config       -> Forge, read-only
Hermes skills      -> Hermes, read-only
Codex skills       -> Forge, read-only
```

Do not use a shared `env_file`. Pass each service only its own environment.
Update ignore rules for `router/.venv/`, `router/dist/`, Python caches, and the
local `.runtime/` directory while keeping `router/uv.lock`, examples, and test
fixtures in both Git and Docker build contexts.

- [ ] **Step 4: Configure Hermes reproducibly**

`config/hermes/configure.py` loads `/opt/data/config.yaml`, preserves unrelated
Hermes state, and sets:

```yaml
model:
  provider: deepseek
  name: deepseek/deepseek-v4-flash
  default: deepseek/deepseek-v4-flash
delegation:
  provider: deepseek
  model: deepseek/deepseek-v4-flash
  max_concurrent_children: 3
  max_spawn_depth: 1
  orchestrator_enabled: true
mcp_servers:
  barbarossa:
    command: /opt/barbarossa-router/barbarossa-router.pex
    args: [serve]
    supports_parallel_tool_calls: true
    connect_timeout: 15
    timeout: 30
    env:
      BARBAROSSA_SSH_KEY: /run/secrets/worker_key
      BARBAROSSA_KNOWN_HOSTS: /run/secrets/known_hosts
      BARBAROSSA_STATE_DB: /opt/data/router/jobs.sqlite3
      BARBAROSSA_INPUT_ROOT: /opt/data/barbarossa-transfer
      BARBAROSSA_RESULT_ROOT: /opt/data/barbarossa-results
      BARBAROSSA_FORGE_HOST: forge
      BARBAROSSA_RECON_HOST: recon
      OTEL_SDK_DISABLED: "true"
```

Write through a temporary file, preserve mode `0600`, and validate the result
with `yaml.safe_load()` before replacement.

- [ ] **Step 5: Write focused routing skills**

The Hermes skills must state:

- use `runtime_execute` for generic shell/toolchain work;
- use `code_delegate` for Codex engineering tasks;
- use image tools only for inspect/generate/edit;
- use direct Recon by default and `network_tor` only explicitly;
- poll jobs instead of starting duplicates;
- never infer success from an empty log;
- copy attachments into `/opt/data/barbarossa-transfer` before submitting
  them and use only paths returned by the router under
  `/opt/data/barbarossa-results`;
- promote valuable artifacts manually to the private repository.

The Codex artifact skill requires generated files under the job's `outputs/`
directory and forbids writing credentials into artifacts.

- [ ] **Step 6: Run Compose and regression validation**

Run:

```bash
mkdir -p /tmp/barbarossa-plan
touch /tmp/barbarossa-plan/{authorized_keys,known_hosts,worker_key,codex_token,router.pex}
chmod 600 /tmp/barbarossa-plan/{worker_key,codex_token}
BARBAROSSA_AUTHORIZED_KEYS_FILE=/tmp/barbarossa-plan/authorized_keys \
BARBAROSSA_KNOWN_HOSTS_FILE=/tmp/barbarossa-plan/known_hosts \
BARBAROSSA_WORKER_SSH_KEY_FILE=/tmp/barbarossa-plan/worker_key \
BARBAROSSA_CODEX_TOKEN_FILE=/tmp/barbarossa-plan/codex_token \
BARBAROSSA_ROUTER_BUNDLE=/tmp/barbarossa-plan/router.pex \
DEEPSEEK_API_KEY=test TELEGRAM_BOT_TOKEN=test \
DASHBOARD_USER=test DASHBOARD_PASS=test DASHBOARD_SECRET=test \
docker compose config --quiet
bash tests/infra-regression.sh
```

Expected: Compose and all regression assertions pass.

- [ ] **Step 7: Commit**

```bash
git add docker-compose.yml config skills AGENTS.md WORKERS.md \
  .env.example .gitignore .dockerignore tests/infra-regression.sh
git commit -m "feat: define hermes forge recon stack"
```

## Task 9: Router PEX Bundle

**Files:**
- Create: `router/Containerfile.bundle`
- Modify: `router/pyproject.toml`
- Test: `router/tests/test_server.py`

- [ ] **Step 1: Add a packaged-server smoke test**

Add a `router/tests/test_packaged_server.py` test which receives
`BARBAROSSA_ROUTER_PEX`, starts that executable through the MCP v2 stdio client
transport, lists tools, and asserts `runtime_execute`, `code_delegate`,
`media_image_generate`, and `network_tor` are present. Skip only when the
environment variable is absent so normal unit runs remain fast.

```python
import os
from pathlib import Path

import pytest
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_packaged_server_lists_expected_tools(tmp_path: Path) -> None:
    executable = os.environ.get("BARBAROSSA_ROUTER_PEX")
    if executable is None:
        pytest.skip("BARBAROSSA_ROUTER_PEX is not set")
    python = os.environ["BARBAROSSA_ROUTER_PYTHON"]
    key = tmp_path / "worker_key"
    known_hosts = tmp_path / "known_hosts"
    key.touch(mode=0o600)
    known_hosts.touch(mode=0o600)
    parameters = StdioServerParameters(
        command=python,
        args=[executable, "serve"],
        env={
            "BARBAROSSA_SSH_KEY": str(key),
            "BARBAROSSA_KNOWN_HOSTS": str(known_hosts),
            "BARBAROSSA_STATE_DB": str(tmp_path / "jobs.sqlite3"),
            "BARBAROSSA_FORGE_HOST": "forge",
            "BARBAROSSA_RECON_HOST": "recon",
        },
    )
    async with Client(stdio_client(parameters)) as client:
        tools = await client.list_tools()
    names = {tool.name for tool in tools.tools}
    assert {
        "runtime_execute",
        "code_delegate",
        "media_image_generate",
        "network_tor",
    } <= names
```

- [ ] **Step 2: Verify it fails before packaging**

Run:

```bash
cd router
BARBAROSSA_ROUTER_PEX="$PWD/dist/barbarossa-router.pex" \
BARBAROSSA_ROUTER_PYTHON="$(command -v python3)" \
  uv run pytest tests/test_packaged_server.py -q
```

Expected: failure because `dist/barbarossa-router.pex` does not exist.

- [ ] **Step 3: Produce a self-contained PEX**

Configure the build to include `barbarossa_router` and all locked runtime
dependencies. Build for Python 3.13 because the pinned Hermes image provides
Python 3.13.5 at `/opt/hermes/.venv/bin/python`.

Create:

```dockerfile
# router/Containerfile.bundle
FROM scratch
COPY dist/barbarossa-router.pex /barbarossa-router.pex
```

This OCI image is a delivery artifact, not a running fourth service.

- [ ] **Step 4: Verify the artifact**

Run:

```bash
cd router
uv python install 3.13
mkdir -p dist
uv export --frozen --no-dev --no-emit-project \
  --format requirements-txt \
  --output-file dist/runtime-requirements.txt
uv run --python 3.13 --with pex==2.98.4 pex \
  -r dist/runtime-requirements.txt . \
  -o dist/barbarossa-router.pex \
  --python-shebang=/opt/hermes/.venv/bin/python \
  -c barbarossa-router
docker run --rm \
  --entrypoint /opt/hermes/.venv/bin/python \
  -v "$PWD/dist:/bundle:ro" \
  nousresearch/hermes-agent@sha256:545ef5a71b52b63aab08e29721701681d64465594ae5ffe7e860a8a758da0371 \
  /bundle/barbarossa-router.pex --help
BARBAROSSA_ROUTER_PEX="$PWD/dist/barbarossa-router.pex" \
BARBAROSSA_ROUTER_PYTHON="$(uv python find 3.13)" \
  uv run pytest tests/test_packaged_server.py -q
```

Expected: CLI help exits zero and MCP tests pass.

- [ ] **Step 5: Commit**

```bash
git add router/Containerfile.bundle router/pyproject.toml \
  router/tests/test_packaged_server.py
git commit -m "build: package router as pex artifact"
```

## Task 10: CI Build And Direct OVH Cutover

**Files:**
- Modify: `.github/workflows/build-deploy.yml`
- Create: `scripts/deploy-runtime-files.sh`
- Create: `scripts/smoke-remote.sh`
- Modify: `tests/infra-regression.sh`

- [ ] **Step 1: Add failing workflow assertions**

Require:

- router tests before packaging;
- Forge and Recon image builds;
- immutable `${{ github.sha }}` tags;
- a router-bundle OCI artifact tagged with the same SHA;
- actions pinned to commit SHAs;
- OVH host fingerprint verification;
- direct removal of the old stack and volumes;
- a fresh worker key on every cutover;
- restricted authorized-key options;
- generated known-hosts before Hermes starts;
- remote smoke tests after deploy;
- no fallback to `StrictHostKeyChecking=no`;
- no secret interpolated into a Git remote or printed environment.

- [ ] **Step 2: Verify regression failure**

Run:

```bash
bash tests/infra-regression.sh
```

Expected: workflow assertions fail against the Charlie/Oscar/Papa build jobs.

- [ ] **Step 3: Build and publish immutable artifacts**

The workflow sequence is:

```text
validate
├── uv sync --frozen
├── pytest
├── infra-regression.sh
└── docker compose config

build-router
├── pex 2.98.4
└── ghcr.io/uphiago/barbarossa-router-bundle:${GITHUB_SHA}

build-workers
├── ghcr.io/uphiago/barbarossa-forge:${GITHUB_SHA}
└── ghcr.io/uphiago/barbarossa-recon:${GITHUB_SHA}

deploy
└── runs only after every prior job succeeds
```

Publish `latest` only as a convenience tag. Production Compose receives the
immutable commit SHA through `BARBAROSSA_IMAGE_TAG`.

- [ ] **Step 4: Implement fresh runtime credentials**

On OVH, `deploy-runtime-files.sh` creates a mode-`0700` directory under:

```text
$HOME/.config/barbarossa/runtime
```

Every deployment generates a new Ed25519 worker key. Construct authorized
keys with:

```bash
printf 'restrict,command="/usr/local/bin/worker-ssh-dispatch" %s\n' \
  "$(cat "$WORKER_KEY.pub")" > "$AUTHORIZED_KEYS"
```

Start Forge and Recon first. Read their public host keys from the persisted
host-key volumes through `docker compose exec`, then write:

```bash
printf 'forge %s\n' \
  "$(docker compose exec -T forge \
      cat /ssh-host-keys/ssh_host_ed25519_key.pub)" \
  > "$KNOWN_HOSTS"
printf 'recon %s\n' \
  "$(docker compose exec -T recon \
      cat /ssh-host-keys/ssh_host_ed25519_key.pub)" \
  >> "$KNOWN_HOSTS"
```

to a mode-`0600` `known_hosts`. Never use `ssh-keyscan` as the source of trust
and never disable strict checking.

- [ ] **Step 5: Implement direct cutover**

On the one-time legacy cutover, the deploy script must:

```bash
docker compose down --remove-orphans
docker rm -f charlie oscar papa hermes 2>/dev/null || true
docker volume rm \
  barbarossa_charlie-data barbarossa_charlie-ssh \
  barbarossa_oscar-data barbarossa_oscar-ssh \
  barbarossa_papa-data barbarossa_papa-ssh barbarossa_papa-tor \
  barbarossa_hermes-data \
  2>/dev/null || true
```

Do not remove `hermes-state`, `forge-workspace`, `forge-codex-home`, or
`recon-workspace` on subsequent deployments. Then pull Forge, Recon, and the
router bundle at the commit SHA. Extract the PEX through a temporary stopped
container, remove that container, start workers, generate known-hosts,
configure Hermes state, and start Hermes. Only Hermes, Forge, and Recon remain
running.

- [ ] **Step 6: Add deterministic remote smoke checks**

`scripts/smoke-remote.sh` verifies:

```bash
docker compose ps --status running --services |
  sort | diff -u - <(printf 'forge\nhermes\nrecon\n')
docker compose exec -T hermes \
  /opt/barbarossa-router/barbarossa-router.pex health
docker compose exec -T hermes \
  /opt/hermes/bin/hermes mcp test barbarossa
```

It then submits and waits for:

- `runtime.execute` with `printf BARBAROSSA_RUNTIME_OK`;
- a minimal Codex response;
- a Codex prompt that spawns one subagent;
- image inspection using the committed tiny PNG fixture;
- image generation with an output file;
- direct Recon fetch to the Tor check API showing `IsTor:false`;
- explicit Tor fetch showing `IsTor:true`.

Finally, inspect networks, mounts, users, Docker socket absence, and redacted
logs. Any failure exits non-zero and fails the deploy workflow.

- [ ] **Step 7: Run workflow regression tests**

Run:

```bash
bash tests/infra-regression.sh
```

Expected: all CI security and cutover assertions pass.

- [ ] **Step 8: Commit**

```bash
git add .github/workflows/build-deploy.yml scripts \
  tests/infra-regression.sh
git commit -m "ci: deploy disposable barbarossa stack"
```

## Task 11: Remove Legacy Workers And Update Operator Docs

**Files:**
- Delete: `workers/`
- Modify: `setup.sh`
- Modify: `README.md`
- Modify: `WORKERS.md`
- Modify: `AGENTS.md`
- Modify: `tests/infra-regression.sh`

- [ ] **Step 1: Add failing legacy-removal assertions**

Assert that:

```bash
test ! -e workers
! grep -R -E '\b(charlie|oscar|papa)\b' \
  docker-compose.yml README.md WORKERS.md AGENTS.md setup.sh
```

Allow legacy names only in the dated design and implementation documents.

- [ ] **Step 2: Verify the assertions fail**

Run:

```bash
bash tests/infra-regression.sh
```

Expected: `workers/` and current docs still reference legacy services.

- [ ] **Step 3: Remove the old implementation**

Run:

```bash
git rm -r workers
```

Do not remove `ops/host`; fail2ban, host SSH restrictions, and the cloud
metadata firewall remain applicable.

- [ ] **Step 4: Rewrite local setup**

`setup.sh` must:

1. validate local prerequisites and required variables;
2. build the router PEX, Forge, and Recon;
3. generate restricted local SSH runtime files;
4. start workers;
5. derive and pin worker host keys;
6. configure Hermes;
7. start Hermes;
8. run the same smoke script in local mode.

It must not copy keys into containers, grant root worker SSH, or use fixed
container names.

- [ ] **Step 5: Rewrite public documentation**

Document:

- Hermes, Forge, Recon roles;
- logical capabilities and lane limits;
- GPT-5.6 medium in Forge;
- Codex primary plus one subagent;
- image inspection/generation/editing;
- direct networking and explicit Tor;
- local volumes without automatic cleanup;
- manual promotion to a separate private repository;
- fresh, deployment-local worker keys;
- direct destructive cutover and absence of state migration.

Do not include live addresses, usernames, tokens, operational evidence, or
private repository names.

- [ ] **Step 6: Run documentation and infra checks**

Run:

```bash
bash tests/infra-regression.sh
git diff --check
```

Expected: all assertions pass and Git reports no whitespace errors.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: remove legacy barbarossa workers"
```

## Task 12: Full Validation And Production Deployment

**Files:**
- Modify only when a failing validation identifies a scoped defect.

- [ ] **Step 1: Run the complete local test suite**

Run:

```bash
cd router && uv sync --frozen && uv run pytest -q
cd ..
uv run --with pytest==9.1.1 pytest tests/test-worker-rpc.py -q
bash tests/infra-regression.sh
bash tests/container-integration.sh all
git diff --check
```

Expected: every command exits zero.

- [ ] **Step 2: Scan the repository**

Run the same pinned Gitleaks version used by CI:

```bash
tmpdir=$(mktemp -d)
curl -fsSLo "$tmpdir/gitleaks.tar.gz" \
  https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz
echo '551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb  '"$tmpdir"'/gitleaks.tar.gz' |
  sha256sum -c -
tar -xzf "$tmpdir/gitleaks.tar.gz" -C "$tmpdir" gitleaks
"$tmpdir/gitleaks" git --log-opts=--all --max-decode-depth=2 \
  --no-banner --redact --verbose .
rm -rf "$tmpdir"
```

Expected: no leaks.

- [ ] **Step 3: Push and inspect GitHub Actions**

Push the implementation branch and use `gh run watch` followed by
`gh run view --log-failed`. Do not begin the OVH cutover while validation or
image publication is incomplete.

Expected: router tests, both image builds, secret scan, and deploy prerequisites
pass.

- [ ] **Step 4: Execute the direct production cutover**

Trigger the deployment workflow for the reviewed commit SHA. The workflow
stops and removes the old stack and volumes before starting the new workers.

Expected: the deploy job reaches the remote smoke stage with exactly three
running services.

- [ ] **Step 5: Review production state and logs**

Run read-only checks through `ssh ovh`:

```bash
docker compose -f ~/barbarossa/docker-compose.yml ps
docker stats --no-stream
docker compose -f ~/barbarossa/docker-compose.yml logs \
  --since 15m --no-color hermes forge recon
sudo fail2ban-client status sshd
sudo journalctl -u barbarossa-container-firewall --since '30 minutes ago'
```

Confirm:

- no crash loops, OOM kills, authentication failures, or repeated MCP restarts;
- Forge and Recon remain below their memory/PID limits;
- no Codex, GitHub, or worker-control secret appears in Hermes or Recon
  inspection output, and no secret appears in logs;
- host SSH forwarding still permits only the Hermes dashboard tunnel;
- fail2ban and metadata blocking remain active.

- [ ] **Step 6: Run user-facing capability checks**

Through Telegram or the configured API, ask Hermes to:

1. delegate runtime and Recon work in parallel;
2. delegate a Codex task while runtime is active;
3. inspect an image;
4. generate an image;
5. use Tor only after an explicit request.

Expected: Hermes selects the correct MCP tools, reports job IDs, polls instead
of duplicating work, and returns artifacts from the expected worker.

- [ ] **Step 7: Record final evidence**

Record only sanitized versions, image digests, test summaries, and the deployed
Git SHA in a private operational note. Do not commit live container logs,
addresses, usernames, or credentials to the public Barbarossa repository.

- [ ] **Step 8: Final commit for scoped validation fixes**

If validation required code changes, rerun Steps 1 and 2, then stage the
tracked files reported by Git and commit only those fixes:

```bash
git diff --name-only -z |
  xargs -0 --no-run-if-empty git add --
git commit -m "fix: address barbarossa deployment validation"
```

If no files changed, do not create an empty commit.
