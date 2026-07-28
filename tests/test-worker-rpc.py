import importlib.util
import io
import json
import os
import tarfile
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[1]
WORKER_RPC_PATH = ROOT / "containers" / "shared" / "worker-rpc.py"
SAFE_JOB_ID = "job_runtime_01J00000000000000000000000"


@pytest.fixture
def worker_rpc(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ModuleType:
    monkeypatch.setenv("WORKSPACE_ROOT", str(tmp_path / "workspace"))
    monkeypatch.setenv("WORKER_HOME", str(tmp_path / "home"))
    spec = importlib.util.spec_from_file_location("worker_rpc", WORKER_RPC_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_workspace_rejects_traversal(
    worker_rpc: ModuleType,
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="invalid job id"):
        worker_rpc.workspace(tmp_path, "../../root")


def test_runtime_environment_contains_no_secret(
    worker_rpc: ModuleType,
) -> None:
    env = worker_rpc.job_environment("runtime.execute")
    assert set(env) == {"HOME", "LANG", "PATH", "TZ"}


def test_codex_argv_is_not_shell_interpolated(
    worker_rpc: ModuleType,
    tmp_path: Path,
) -> None:
    job = worker_rpc.workspace(tmp_path, SAFE_JOB_ID)
    job.inputs.mkdir(parents=True)
    job.outputs.mkdir()

    argv = worker_rpc.build_argv(
        job,
        {
            "capability": "code.delegate",
            "prompt": "review; touch /tmp/pwned",
        },
    )

    assert argv[0:2] == ["codex", "exec"]
    assert argv[-1] == "review; touch /tmp/pwned"


def test_fetch_argv_validates_http_url(worker_rpc: ModuleType, tmp_path: Path) -> None:
    job = worker_rpc.workspace(tmp_path, SAFE_JOB_ID)
    job.inputs.mkdir(parents=True)
    job.outputs.mkdir()

    with pytest.raises(ValueError, match="http"):
        worker_rpc.build_argv(
            job,
            {"capability": "network.fetch", "url": "file:///etc/passwd"},
        )


def _archive(members: list[tuple[tarfile.TarInfo, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:") as archive:
        for info, contents in members:
            info.size = len(contents)
            archive.addfile(info, io.BytesIO(contents))
    return buffer.getvalue()


def test_upload_extracts_regular_top_level_files(
    worker_rpc: ModuleType,
) -> None:
    info = tarfile.TarInfo("diagram.png")

    names = worker_rpc.extract_upload(
        SAFE_JOB_ID,
        io.BytesIO(_archive([(info, b"png")])),
    )

    job = worker_rpc.workspace(worker_rpc.WORKSPACE_ROOT, SAFE_JOB_ID)
    assert names == ["diagram.png"]
    assert (job.inputs / "diagram.png").read_bytes() == b"png"


@pytest.mark.parametrize("name", ["../secret", "/etc/passwd", "dir/file"])
def test_upload_rejects_unsafe_paths(
    worker_rpc: ModuleType,
    name: str,
) -> None:
    with pytest.raises(ValueError):
        worker_rpc.extract_upload(
            SAFE_JOB_ID,
            io.BytesIO(_archive([(tarfile.TarInfo(name), b"bad")])),
        )


def test_download_redacts_logs_and_excludes_inputs(
    worker_rpc: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BARBAROSSA_REDACT_VALUES", "top-secret")
    job = worker_rpc.workspace(worker_rpc.WORKSPACE_ROOT, SAFE_JOB_ID)
    job.inputs.mkdir(parents=True)
    job.outputs.mkdir()
    (job.inputs / "private.txt").write_text("private", encoding="utf-8")
    (job.outputs / "report.txt").write_text("ok", encoding="utf-8")
    job.stdout.write_text("token top-secret", encoding="utf-8")
    job.stderr.write_text("", encoding="utf-8")
    job.result.write_text(
        json.dumps({"status": "succeeded"}),
        encoding="utf-8",
    )

    archive_bytes = worker_rpc.create_download(SAFE_JOB_ID)

    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
        assert sorted(archive.getnames()) == [
            "outputs/report.txt",
            "result.json",
            "stderr.log",
            "stdout.log",
        ]
        assert b"top-secret" not in archive.extractfile("stdout.log").read()
        assert "inputs/private.txt" not in archive.getnames()


def test_start_and_run_runtime_job(
    worker_rpc: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(worker_rpc, "launch_supervisor", lambda job_id: os.getpid())
    response = worker_rpc.start_job(
        SAFE_JOB_ID,
        {
            "capability": "runtime.execute",
            "command": "printf test",
            "lane": "runtime",
        },
    )
    assert response["status"] == "running"
    assert response["remote_pid"] == os.getpid()

    monkeypatch.setattr(
        worker_rpc,
        "process_start_time",
        lambda pid: response["process_start_time"],
    )
    status = worker_rpc.read_status(SAFE_JOB_ID)
    assert status["status"] == "running"


def test_run_runtime_job_records_result(
    worker_rpc: ModuleType,
) -> None:
    job = worker_rpc.workspace(worker_rpc.WORKSPACE_ROOT, SAFE_JOB_ID)
    job.inputs.mkdir(parents=True)
    job.outputs.mkdir()
    job.stdout.touch()
    job.stderr.touch()
    worker_rpc.atomic_json(
        job.request,
        {
            "capability": "runtime.execute",
            "command": "printf completed",
            "lane": "runtime",
        },
    )

    assert worker_rpc.run_job(SAFE_JOB_ID) == 0
    assert job.stdout.read_text(encoding="utf-8") == "completed"
    assert worker_rpc.load_json(job.result)["status"] == "succeeded"


def test_lane_lock_rejects_second_job(
    worker_rpc: ModuleType,
) -> None:
    import fcntl

    job = worker_rpc.workspace(worker_rpc.WORKSPACE_ROOT, SAFE_JOB_ID)
    job.inputs.mkdir(parents=True)
    job.outputs.mkdir()
    job.stdout.touch()
    job.stderr.touch()
    worker_rpc.atomic_json(
        job.request,
        {
            "capability": "runtime.execute",
            "command": "true",
            "lane": "runtime",
        },
    )
    lock_root = worker_rpc.WORKSPACE_ROOT / ".locks"
    lock_root.mkdir(parents=True)
    with (lock_root / "runtime.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert worker_rpc.run_job(SAFE_JOB_ID) == 75

    result = worker_rpc.load_json(job.result)
    assert result["status"] == "failed"
    assert "already active" in result["error"]


def test_download_rejects_output_symlink(
    worker_rpc: ModuleType,
    tmp_path: Path,
) -> None:
    job = worker_rpc.workspace(worker_rpc.WORKSPACE_ROOT, SAFE_JOB_ID)
    job.outputs.mkdir(parents=True)
    target = tmp_path / "secret"
    target.write_text("secret", encoding="utf-8")
    (job.outputs / "link").symlink_to(target)

    with pytest.raises(ValueError, match="symbolic link"):
        worker_rpc.create_download(SAFE_JOB_ID)


def test_dispatcher_denies_arbitrary_commands() -> None:
    dispatcher = (
        ROOT / "containers" / "shared" / "worker-ssh-dispatch.sh"
    )
    result = __import__("subprocess").run(
        [str(dispatcher)],
        env={"SSH_ORIGINAL_COMMAND": "sh -c id", "PATH": os.environ["PATH"]},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 126
    assert result.stderr == "command denied\n"


def test_rpc_rejects_unknown_action(worker_rpc: ModuleType) -> None:
    with pytest.raises(ValueError, match="unsupported action"):
        worker_rpc.handle_rpc({"action": "delete-everything"})
