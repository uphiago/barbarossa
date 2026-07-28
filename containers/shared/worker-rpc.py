#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, NamedTuple
from urllib.parse import urlparse

WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", "/workspace")).resolve()
WORKER_HOME = Path(os.environ.get("WORKER_HOME", str(Path.home()))).resolve()
SAFE_PATH = (
    "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
)
MAX_RPC_BYTES = 1024 * 1024
MAX_INPUT_BYTES = 32 * 1024 * 1024
MAX_OUTPUT_BYTES = 64 * 1024 * 1024
MAX_LOG_BYTES = 200_000
JOB_ID_RE = re.compile(
    r"^job_(runtime|codex|image|recon)_[0-9A-HJKMNP-TV-Z]{26}$"
)
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

CAPABILITY_LANES = {
    "runtime.execute": "runtime",
    "media.file.inspect": "runtime",
    "code.delegate": "codex",
    "media.image.inspect": "codex",
    "media.image.generate": "codex",
    "media.image.edit": "codex",
    "network.inspect": "recon",
    "network.fetch": "recon",
    "network.tor": "recon",
}
FORGE_CAPABILITIES = {
    capability
    for capability, lane in CAPABILITY_LANES.items()
    if lane != "recon"
}
RECON_CAPABILITIES = {
    capability
    for capability, lane in CAPABILITY_LANES.items()
    if lane == "recon"
}
TERMINAL_STATES = {"succeeded", "failed", "cancelled", "interrupted"}


class JobPaths(NamedTuple):
    root: Path
    inputs: Path
    outputs: Path
    request: Path
    status: Path
    stdout: Path
    stderr: Path
    result: Path


def validate_job_id(job_id: str) -> str:
    if not isinstance(job_id, str) or not JOB_ID_RE.fullmatch(job_id):
        raise ValueError("invalid job id")
    return job_id


def workspace(root: Path, job_id: str) -> JobPaths:
    validate_job_id(job_id)
    job_root = root.resolve() / "jobs" / job_id
    return JobPaths(
        root=job_root,
        inputs=job_root / "inputs",
        outputs=job_root / "outputs",
        request=job_root / "request.json",
        status=job_root / "status.json",
        stdout=job_root / "stdout.log",
        stderr=job_root / "stderr.log",
        result=job_root / "result.json",
    )


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing worker state: {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid worker state: {path.name}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"invalid worker state: {path.name}")
    return value


def process_start_time(pid: int) -> int:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
        tail = raw.rsplit(") ", 1)[1].split()
        return int(tail[19])
    except (FileNotFoundError, IndexError, ValueError) as exc:
        raise ProcessLookupError(pid) from exc


def process_matches(pid: int, expected_start_time: int) -> bool:
    try:
        return process_start_time(pid) == expected_start_time
    except ProcessLookupError:
        return False


def job_environment(capability: str) -> dict[str, str]:
    environment = {
        "HOME": str(WORKER_HOME),
        "LANG": "C.UTF-8",
        "PATH": SAFE_PATH,
        "TZ": os.environ.get("TZ", "UTC"),
    }
    if capability.startswith(("code.", "media.image.")):
        environment["CODEX_HOME"] = os.environ.get(
            "CODEX_HOME",
            str(WORKER_HOME / ".codex"),
        )
        for variable, default_path in (
            ("CODEX_ACCESS_TOKEN", "/run/secrets/codex_access_token"),
            ("GH_TOKEN", "/run/secrets/github_token"),
        ):
            secret_path = Path(
                os.environ.get(f"{variable}_FILE", default_path)
            )
            if secret_path.is_file():
                value = secret_path.read_text(encoding="utf-8").removesuffix(
                    "\n"
                )
                if not value or "\n" in value or "\r" in value:
                    raise ValueError(f"{variable} secret is malformed")
                environment[variable] = value
    return environment


def require_text(request: dict[str, Any], field: str) -> str:
    value = request.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} is required")
    return value


def single_input(job: JobPaths, request: dict[str, Any]) -> Path:
    inputs = request.get("input_paths")
    if (
        not isinstance(inputs, list)
        or len(inputs) != 1
        or not isinstance(inputs[0], str)
        or not SAFE_NAME_RE.fullmatch(inputs[0])
    ):
        raise ValueError("capability requires one valid input")
    path = job.inputs / inputs[0]
    if not path.is_file() or path.is_symlink():
        raise ValueError("input file is missing")
    return path


def build_argv(job: JobPaths, request: dict[str, Any]) -> list[str]:
    capability = request.get("capability")
    if capability == "runtime.execute":
        return ["/bin/bash", "-lc", require_text(request, "command")]
    if capability == "media.file.inspect":
        path = single_input(job, request)
        return ["file", "--brief", "--mime", "--", str(path)]
    if capability == "code.delegate":
        return [
            "codex",
            "exec",
            "--strict-config",
            "--skip-git-repo-check",
            "--json",
            "--output-last-message",
            str(job.outputs / "final.txt"),
            "--cd",
            str(job.root),
            require_text(request, "prompt"),
        ]
    if capability in {"media.image.inspect", "media.image.edit"}:
        path = single_input(job, request)
        prompt = require_text(request, "prompt")
        if capability == "media.image.edit":
            prompt = (
                f"$imagegen {prompt}\nEdit the attached image at {path}. "
                f"Save the final image under {job.outputs}."
            )
        return [
            "codex",
            "exec",
            "--strict-config",
            "--skip-git-repo-check",
            "--json",
            "--output-last-message",
            str(job.outputs / "final.txt"),
            "--image",
            str(path),
            "--cd",
            str(job.root),
            prompt,
        ]
    if capability == "media.image.generate":
        prompt = (
            f"$imagegen {require_text(request, 'prompt')}\n"
            "Save the final image under "
            f"{job.outputs}."
        )
        return [
            "codex",
            "exec",
            "--strict-config",
            "--skip-git-repo-check",
            "--json",
            "--output-last-message",
            str(job.outputs / "final.txt"),
            "--cd",
            str(job.root),
            prompt,
        ]
    if capability == "network.inspect":
        return ["/bin/bash", "-lc", require_text(request, "command")]
    if capability == "network.tor":
        return [
            "torsocks",
            "--isolate",
            "/bin/bash",
            "-lc",
            require_text(request, "command"),
        ]
    if capability == "network.fetch":
        url = require_text(request, "url")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("network.fetch requires an http(s) URL")
        return [
            "curl",
            "--fail-with-body",
            "--location",
            "--max-time",
            "120",
            "--proto",
            "=http,https",
            "--output",
            str(job.outputs / "response.bin"),
            "--dump-header",
            str(job.outputs / "headers.txt"),
            "--",
            url,
        ]
    raise ValueError("unsupported capability")


def validate_request(request: Any) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise ValueError("request must be an object")
    capability = request.get("capability")
    if capability not in CAPABILITY_LANES:
        raise ValueError("unsupported capability")
    expected_lane = CAPABILITY_LANES[capability]
    if request.get("lane") != expected_lane:
        raise ValueError("capability lane mismatch")
    worker_kind = os.environ.get("WORKER_KIND")
    if worker_kind == "forge" and capability not in FORGE_CAPABILITIES:
        raise ValueError("capability is not available on forge")
    if worker_kind == "recon" and capability not in RECON_CAPABILITIES:
        raise ValueError("capability is not available on recon")
    return request


def launch_supervisor(job_id: str) -> int:
    environment = job_environment("runtime.execute")
    environment.update(
        {
            "WORKSPACE_ROOT": str(WORKSPACE_ROOT),
            "WORKER_HOME": str(WORKER_HOME),
            "WORKER_KIND": os.environ.get("WORKER_KIND", ""),
        }
    )
    process = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "run-job", job_id],
        cwd=workspace(WORKSPACE_ROOT, job_id).root,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return process.pid


def start_job(job_id: str, raw_request: Any) -> dict[str, Any]:
    job = workspace(WORKSPACE_ROOT, job_id)
    request = validate_request(raw_request)
    job.inputs.mkdir(parents=True, exist_ok=True)
    job.outputs.mkdir(parents=True, exist_ok=True)
    if job.request.exists():
        return read_status(job_id)
    atomic_json(job.request, request)
    job.stdout.touch(mode=0o600, exist_ok=True)
    job.stderr.touch(mode=0o600, exist_ok=True)
    atomic_json(job.status, {"status": "starting", "job_id": job_id})
    pid = launch_supervisor(job_id)
    try:
        started = process_start_time(pid)
    except ProcessLookupError as exc:
        atomic_json(
            job.result,
            {
                "status": "failed",
                "exit_code": None,
                "artifacts": [],
                "error": "supervisor exited during startup",
            },
        )
        raise RuntimeError("supervisor exited during startup") from exc
    status = {
        "status": "running",
        "job_id": job_id,
        "remote_pid": pid,
        "process_start_time": started,
    }
    atomic_json(job.status, status)
    return status


def read_status(job_id: str) -> dict[str, Any]:
    job = workspace(WORKSPACE_ROOT, job_id)
    if job.result.exists():
        return load_json(job.result)
    status = load_json(job.status)
    if status.get("status") == "running":
        pid = status.get("remote_pid")
        started = status.get("process_start_time")
        if (
            not isinstance(pid, int)
            or not isinstance(started, int)
            or not process_matches(pid, started)
        ):
            result = {
                "status": "interrupted",
                "exit_code": None,
                "artifacts": artifact_names(job),
                "error": "supervisor process is no longer running",
            }
            atomic_json(job.result, result)
            return result
    return status


def artifact_names(job: JobPaths) -> list[str]:
    if not job.outputs.exists():
        return []
    artifacts: list[str] = []
    for path in sorted(job.outputs.rglob("*")):
        if path.is_file() and not path.is_symlink():
            artifacts.append(str(path.relative_to(job.root)))
    return artifacts


def run_job(job_id: str) -> int:
    job = workspace(WORKSPACE_ROOT, job_id)
    request = validate_request(load_json(job.request))
    lane = CAPABILITY_LANES[request["capability"]]
    lock_root = WORKSPACE_ROOT / ".locks"
    lock_root.mkdir(parents=True, exist_ok=True)
    cancelled = False

    def mark_cancelled(_signum: int, _frame: Any) -> None:
        nonlocal cancelled
        cancelled = True

    signal.signal(signal.SIGTERM, mark_cancelled)
    signal.signal(signal.SIGINT, mark_cancelled)
    with (lock_root / f"{lane}.lock").open("w", encoding="ascii") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            atomic_json(
                job.result,
                {
                    "status": "failed",
                    "exit_code": None,
                    "artifacts": artifact_names(job),
                    "error": f"{lane} lane is already active",
                },
            )
            return 75
        try:
            argv = build_argv(job, request)
            with (
                job.stdout.open("ab", buffering=0) as stdout,
                job.stderr.open("ab", buffering=0) as stderr,
            ):
                child = subprocess.Popen(
                    argv,
                    cwd=job.root,
                    env=job_environment(request["capability"]),
                    stdin=subprocess.DEVNULL,
                    stdout=stdout,
                    stderr=stderr,
                    close_fds=True,
                )
                exit_code = child.wait()
            state = "cancelled" if cancelled else (
                "succeeded" if exit_code == 0 else "failed"
            )
            atomic_json(
                job.result,
                {
                    "status": state,
                    "exit_code": exit_code,
                    "artifacts": artifact_names(job),
                    "error": None if state != "failed" else "command failed",
                },
            )
            return exit_code
        except Exception as exc:
            atomic_json(
                job.result,
                {
                    "status": "cancelled" if cancelled else "failed",
                    "exit_code": None,
                    "artifacts": artifact_names(job),
                    "error": None if cancelled else str(exc)[:1000],
                },
            )
            return 1


def cancel_job(job_id: str) -> dict[str, Any]:
    job = workspace(WORKSPACE_ROOT, job_id)
    current = read_status(job_id)
    if current.get("status") in TERMINAL_STATES:
        return current
    pid = current.get("remote_pid")
    started = current.get("process_start_time")
    if not isinstance(pid, int) or not isinstance(started, int):
        raise ValueError("worker has no valid supervisor identity")
    if process_matches(pid, started):
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and process_matches(pid, started):
            if job.result.exists():
                return load_json(job.result)
            time.sleep(0.1)
        if process_matches(pid, started):
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    if not job.result.exists():
        atomic_json(
            job.result,
            {
                "status": "cancelled",
                "exit_code": None,
                "artifacts": artifact_names(job),
                "error": None,
            },
        )
    return load_json(job.result)


def redact(data: bytes) -> bytes:
    text = data.decode("utf-8", errors="replace")
    values = [
        value
        for value in os.environ.get("BARBAROSSA_REDACT_VALUES", "").split("\n")
        if len(value) >= 4
    ]
    for value in values:
        text = text.replace(value, "[REDACTED]")
    text = re.sub(
        r"(?i)(authorization\s*:\s*(?:bearer|basic)\s+)\S+",
        r"\1[REDACTED]",
        text,
    )
    text = re.sub(
        r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S+",
        r"\1=[REDACTED]",
        text,
    )
    return text.encode("utf-8")[:MAX_LOG_BYTES]


def read_logs(job_id: str) -> dict[str, Any]:
    job = workspace(WORKSPACE_ROOT, job_id)
    stdout = redact(read_bounded(job.stdout, MAX_LOG_BYTES + 1))
    stderr = redact(read_bounded(job.stderr, MAX_LOG_BYTES + 1))
    return {
        "status": read_status(job_id).get("status"),
        "stdout": stdout.decode("utf-8", errors="replace"),
        "stderr": stderr.decode("utf-8", errors="replace"),
        "truncated": (
            (job.stdout.exists() and job.stdout.stat().st_size > len(stdout))
            or (job.stderr.exists() and job.stderr.stat().st_size > len(stderr))
        ),
    }


def read_bounded(path: Path, limit: int) -> bytes:
    if not path.exists():
        return b""
    with path.open("rb") as stream:
        return stream.read(limit)


def extract_upload(job_id: str, source: BinaryIO) -> list[str]:
    job = workspace(WORKSPACE_ROOT, job_id)
    job.root.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=".inputs.", dir=job.root)
    )
    names: list[str] = []
    total = 0
    try:
        with tarfile.open(fileobj=source, mode="r:*") as archive:
            members = archive.getmembers()
            if len(members) > 8:
                raise ValueError("upload contains too many files")
            seen: set[str] = set()
            for member in members:
                path = PurePosixPath(member.name)
                if (
                    len(path.parts) != 1
                    or not SAFE_NAME_RE.fullmatch(member.name)
                    or not member.isfile()
                ):
                    raise ValueError("upload contains an unsafe member")
                if member.name in seen:
                    raise ValueError("upload contains duplicate filenames")
                seen.add(member.name)
                total += member.size
                if total > MAX_INPUT_BYTES:
                    raise ValueError("upload exceeds the input limit")
                if (job.inputs / member.name).exists():
                    raise ValueError("upload would replace an existing input")
            for member in members:
                destination = temporary / member.name
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise ValueError("upload member has no contents")
                with destination.open("xb") as output:
                    remaining = member.size
                    while remaining:
                        chunk = extracted.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise ValueError("upload member is truncated")
                        output.write(chunk)
                        remaining -= len(chunk)
                os.chmod(destination, 0o600)
                names.append(member.name)
        job.inputs.mkdir(mode=0o700, exist_ok=True)
        for name in names:
            os.replace(temporary / name, job.inputs / name)
        return names
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def add_bytes(
    archive: tarfile.TarFile,
    name: str,
    contents: bytes,
) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(contents)
    info.mode = 0o600
    info.mtime = 0
    archive.addfile(info, io.BytesIO(contents))


def create_download(job_id: str) -> bytes:
    job = workspace(WORKSPACE_ROOT, job_id)
    buffer = io.BytesIO()
    total = 0
    with tarfile.open(fileobj=buffer, mode="w:") as archive:
        if job.outputs.exists():
            for path in sorted(job.outputs.rglob("*")):
                if path.is_symlink():
                    raise ValueError("output contains a symbolic link")
                if not path.is_file():
                    continue
                size = path.stat().st_size
                if total + size > MAX_OUTPUT_BYTES:
                    raise ValueError("download exceeds the output limit")
                contents = path.read_bytes()
                total += len(contents)
                name = (Path("outputs") / path.relative_to(job.outputs)).as_posix()
                add_bytes(archive, name, contents)
        for name, path, should_redact in (
            ("stdout.log", job.stdout, True),
            ("stderr.log", job.stderr, True),
            ("result.json", job.result, False),
        ):
            contents = path.read_bytes() if path.exists() else b""
            if should_redact:
                contents = redact(contents)
            total += len(contents)
            if total > MAX_OUTPUT_BYTES:
                raise ValueError("download exceeds the output limit")
            add_bytes(archive, name, contents)
    if len(buffer.getvalue()) > MAX_OUTPUT_BYTES:
        raise ValueError("download archive exceeds the output limit")
    return buffer.getvalue()


def handle_rpc(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("RPC payload must be an object")
    action = payload.get("action")
    if action == "health":
        return {"status": "ok", "worker": os.environ.get("WORKER_KIND")}
    if action not in {"start", "status", "logs", "cancel", "result"}:
        raise ValueError("unsupported action")
    job_id = validate_job_id(payload.get("job_id"))
    if action == "start":
        return start_job(job_id, payload.get("request"))
    if action == "status":
        return read_status(job_id)
    if action == "logs":
        return read_logs(job_id)
    if action == "cancel":
        return cancel_job(job_id)
    if action == "result":
        return read_status(job_id)
    raise AssertionError("unreachable RPC action")


def rpc_main() -> int:
    raw = sys.stdin.buffer.read(MAX_RPC_BYTES + 1)
    if len(raw) > MAX_RPC_BYTES:
        raise ValueError("RPC request exceeds the size limit")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("RPC request is malformed") from exc
    response = handle_rpc(payload)
    sys.stdout.write(json.dumps(response, ensure_ascii=True, separators=(",", ":")))
    sys.stdout.write("\n")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        raise ValueError("worker command is required")
    command = sys.argv[1]
    if command == "rpc" and len(sys.argv) == 2:
        return rpc_main()
    if command == "run-job" and len(sys.argv) == 3:
        return run_job(validate_job_id(sys.argv[2]))
    if command == "upload" and len(sys.argv) == 3:
        extract_upload(validate_job_id(sys.argv[2]), sys.stdin.buffer)
        return 0
    if command == "download" and len(sys.argv) == 3:
        sys.stdout.buffer.write(create_download(validate_job_id(sys.argv[2])))
        return 0
    if command == "self-test" and len(sys.argv) == 2:
        validate_job_id("job_runtime_01J00000000000000000000000")
        if not WORKSPACE_ROOT.is_absolute() or not WORKER_HOME.is_absolute():
            raise ValueError("worker paths must be absolute")
        sys.stdout.write('{"status":"ok"}\n')
        return 0
    raise ValueError("unsupported worker command")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        sys.stderr.write(f"barbarossa-worker: {error}\n")
        raise SystemExit(1)
