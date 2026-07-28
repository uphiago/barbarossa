import io
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from barbarossa_router.config import Settings
from barbarossa_router.models import JobRequest
from barbarossa_router.ssh import SSHTransport

SAFE_JOB_ID = "job_runtime_01J00000000000000000000000"


class FakeConnection:
    def __init__(self) -> None:
        self.calls: list[SimpleNamespace] = []
        self.responses: list[SimpleNamespace] = []

    async def run(
        self,
        command: str,
        *,
        input: str | bytes,
        check: bool,
        encoding: str | None = "utf-8",
    ) -> SimpleNamespace:
        self.calls.append(
            SimpleNamespace(
                command=command,
                input=input,
                check=check,
                encoding=encoding,
            )
        )
        if self.responses:
            return self.responses.pop(0)
        return SimpleNamespace(
            exit_status=0,
            stdout=json.dumps({"status": "running", "remote_pid": 101}),
            stderr="",
        )

    def is_closed(self) -> bool:
        return False

    def close(self) -> None:
        return None

    async def wait_closed(self) -> None:
        return None


class FakeConnector:
    def __init__(self) -> None:
        self.connections: list[FakeConnection] = []
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> FakeConnection:
        self.calls.append(kwargs)
        connection = FakeConnection()
        self.connections.append(connection)
        return connection


@pytest.fixture
def ssh_settings(tmp_path: Path) -> Settings:
    key = tmp_path / "secrets" / "worker_key"
    known_hosts = tmp_path / "secrets" / "known_hosts"
    key.parent.mkdir()
    key.write_text("private", encoding="utf-8")
    known_hosts.write_text("forge ssh-ed25519 AAAA\n", encoding="utf-8")
    input_root = tmp_path / "transfer"
    result_root = tmp_path / "results"
    input_root.mkdir()
    result_root.mkdir()
    return Settings(
        ssh_key=key,
        known_hosts=known_hosts,
        state_db=tmp_path / "state" / "jobs.sqlite3",
        input_root=input_root,
        result_root=result_root,
    )


async def test_payload_is_sent_on_stdin(
    ssh_settings: Settings,
) -> None:
    connector = FakeConnector()
    transport = SSHTransport(ssh_settings, connector=connector)

    await transport.rpc(
        "forge",
        {"action": "status", "job_id": SAFE_JOB_ID},
    )

    connect = connector.calls[0]
    call = connector.connections[0].calls[0]
    assert connect["host"] == "forge"
    assert connect["username"] == "forge"
    assert connect["known_hosts"] == str(ssh_settings.known_hosts)
    assert call.command == "barbarossa-worker rpc"
    assert json.loads(call.input)["job_id"] == SAFE_JOB_ID


async def test_prompt_never_enters_ssh_command_line(
    ssh_settings: Settings,
) -> None:
    connector = FakeConnector()
    transport = SSHTransport(ssh_settings, connector=connector)
    request = JobRequest(
        capability="code.delegate",
        prompt="review; touch /tmp/not-executed",
    )

    await transport.start("forge", SAFE_JOB_ID, request)

    call = connector.connections[0].calls[0]
    assert call.command == "barbarossa-worker rpc"
    assert "touch" not in call.command
    assert json.loads(call.input)["request"]["prompt"] == request.prompt


async def test_recon_uses_recon_identity(ssh_settings: Settings) -> None:
    connector = FakeConnector()
    transport = SSHTransport(ssh_settings, connector=connector)

    await transport.rpc(
        "recon",
        {"action": "status", "job_id": SAFE_JOB_ID},
    )

    assert connector.calls[0]["host"] == "recon"
    assert connector.calls[0]["username"] == "recon"


async def test_upload_rejects_path_outside_input_root(
    ssh_settings: Settings,
    tmp_path: Path,
) -> None:
    connector = FakeConnector()
    transport = SSHTransport(ssh_settings, connector=connector)
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")

    with pytest.raises(ValueError, match="outside the transfer root"):
        await transport.upload("forge", SAFE_JOB_ID, [str(outside)])

    assert connector.calls == []


async def test_upload_uses_sanitized_tar_on_stdin(
    ssh_settings: Settings,
) -> None:
    connector = FakeConnector()
    transport = SSHTransport(ssh_settings, connector=connector)
    source = ssh_settings.input_root / "diagram.png"
    source.write_bytes(b"png")

    uploaded = await transport.upload(
        "forge",
        SAFE_JOB_ID,
        [str(source)],
    )

    call = connector.connections[0].calls[0]
    assert call.command == f"barbarossa-worker upload {SAFE_JOB_ID}"
    assert call.encoding is None
    with tarfile.open(fileobj=io.BytesIO(call.input), mode="r:") as archive:
        assert archive.getnames() == ["diagram.png"]
        assert archive.extractfile("diagram.png").read() == b"png"
    assert uploaded == ["diagram.png"]


def make_archive(
    members: list[tuple[tarfile.TarInfo, bytes]],
) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:") as archive:
        for info, contents in members:
            info.size = len(contents)
            archive.addfile(info, io.BytesIO(contents))
    return buffer.getvalue()


def test_download_extracts_only_expected_result_members(
    ssh_settings: Settings,
) -> None:
    transport = SSHTransport(ssh_settings, connector=FakeConnector())
    artifact = tarfile.TarInfo("outputs/report.txt")
    result = tarfile.TarInfo("result.json")

    paths = transport._extract_result(
        SAFE_JOB_ID,
        make_archive([(artifact, b"report"), (result, b"{}")]),
    )

    destination = ssh_settings.result_root / SAFE_JOB_ID
    assert (destination / "outputs" / "report.txt").read_bytes() == b"report"
    assert (destination / "result.json").read_bytes() == b"{}"
    assert paths == [
        str(destination / "outputs" / "report.txt"),
        str(destination / "result.json"),
    ]


@pytest.mark.parametrize(
    "member_name",
    [
        "../secret",
        "/etc/passwd",
        "outputs/../../secret",
        "unexpected.txt",
    ],
)
def test_download_rejects_unsafe_archive_paths(
    ssh_settings: Settings,
    member_name: str,
) -> None:
    transport = SSHTransport(ssh_settings, connector=FakeConnector())

    with pytest.raises(ValueError):
        transport._extract_result(
            SAFE_JOB_ID,
            make_archive([(tarfile.TarInfo(member_name), b"bad")]),
        )

    assert not (ssh_settings.result_root / SAFE_JOB_ID).exists()


def test_download_rejects_links(
    ssh_settings: Settings,
) -> None:
    transport = SSHTransport(ssh_settings, connector=FakeConnector())
    link = tarfile.TarInfo("outputs/link")
    link.type = tarfile.SYMTYPE
    link.linkname = "/etc/passwd"

    with pytest.raises(ValueError, match="unsafe member"):
        transport._extract_result(
            SAFE_JOB_ID,
            make_archive([(link, b"")]),
        )
