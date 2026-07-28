import io
import json
import re
import shutil
import stat
import tarfile
from collections.abc import Awaitable, Callable
from pathlib import Path, PurePosixPath
from typing import Any

import asyncssh

from barbarossa_router.config import Settings
from barbarossa_router.models import (
    JOB_ID_PATTERN,
    JobRequest,
    Worker,
)
from barbarossa_router.redaction import Redactor

Connector = Callable[..., Awaitable[Any]]

_JOB_ID_RE = re.compile(JOB_ID_PATTERN)
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_RPC_LIMIT = 1024 * 1024


class SSHTransport:
    def __init__(
        self,
        settings: Settings,
        *,
        connector: Connector = asyncssh.connect,
        redactor: Redactor | None = None,
    ) -> None:
        self.settings = settings
        self._connector = connector
        self._redactor = redactor or Redactor(
            [],
            max_bytes=settings.max_log_bytes,
        )
        self._connections: dict[Worker, Any] = {}

    def _worker(self, worker: Worker) -> tuple[str, str]:
        if worker == "forge":
            return self.settings.forge_host, "forge"
        if worker == "recon":
            return self.settings.recon_host, "recon"
        raise ValueError(f"unknown worker: {worker}")

    async def _connection(self, worker: Worker) -> Any:
        current = self._connections.get(worker)
        if current is not None and not current.is_closed():
            return current
        host, username = self._worker(worker)
        connection = await self._connector(
            host=host,
            port=22,
            username=username,
            client_keys=[self.settings.ssh_key],
            known_hosts=str(self.settings.known_hosts),
            agent_path=None,
            preferred_auth=["publickey"],
            connect_timeout=10,
            keepalive_interval=30,
            keepalive_count_max=3,
        )
        self._connections[worker] = connection
        return connection

    async def close(self) -> None:
        connections = list(self._connections.values())
        self._connections.clear()
        for connection in connections:
            connection.close()
        for connection in connections:
            await connection.wait_closed()

    async def rpc(
        self,
        worker: Worker,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        serialized = json.dumps(
            payload,
            ensure_ascii=True,
            separators=(",", ":"),
        )
        result = await self._run(
            worker,
            "barbarossa-worker rpc",
            input_data=serialized,
            encoding="utf-8",
        )
        stdout = self._text(result.stdout)
        stderr = self._text(result.stderr)
        if result.exit_status != 0:
            detail = self._redactor.clean(stderr or stdout)
            raise RuntimeError(
                f"{worker} RPC failed with exit {result.exit_status}: {detail}"
            )
        if len(stdout.encode()) > _RPC_LIMIT:
            raise RuntimeError(f"{worker} RPC response exceeded {_RPC_LIMIT} bytes")
        try:
            response = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{worker} returned malformed JSON") from exc
        if not isinstance(response, dict):
            raise RuntimeError(f"{worker} returned a non-object response")
        return response

    async def _run(
        self,
        worker: Worker,
        command: str,
        *,
        input_data: str | bytes,
        encoding: str | None,
    ) -> Any:
        connection = await self._connection(worker)
        try:
            return await connection.run(
                command,
                input=input_data,
                check=False,
                encoding=encoding,
            )
        except Exception:
            self._connections.pop(worker, None)
            connection.close()
            raise

    @staticmethod
    def _text(value: str | bytes) -> str:
        if isinstance(value, bytes):
            return value.decode(errors="replace")
        return value

    async def start(
        self,
        worker: Worker,
        job_id: str,
        request: JobRequest,
    ) -> dict[str, Any]:
        self._validate_job_id(job_id)
        staged_names: list[str] = []
        if request.input_paths:
            staged_names = await self.upload(
                worker,
                job_id,
                request.input_paths,
            )
        remote_request = request.model_copy(
            update={"input_paths": staged_names}
        )
        return await self.rpc(
            worker,
            {
                "action": "start",
                "job_id": job_id,
                "request": remote_request.model_dump(mode="json"),
            },
        )

    async def status(
        self,
        worker: Worker,
        job_id: str,
    ) -> dict[str, Any]:
        self._validate_job_id(job_id)
        return await self.rpc(
            worker,
            {"action": "status", "job_id": job_id},
        )

    async def cancel(
        self,
        worker: Worker,
        job_id: str,
    ) -> dict[str, Any]:
        self._validate_job_id(job_id)
        return await self.rpc(
            worker,
            {"action": "cancel", "job_id": job_id},
        )

    async def logs(
        self,
        worker: Worker,
        job_id: str,
    ) -> dict[str, Any]:
        self._validate_job_id(job_id)
        return await self.rpc(
            worker,
            {"action": "logs", "job_id": job_id},
        )

    async def remote_result(
        self,
        worker: Worker,
        job_id: str,
    ) -> dict[str, Any]:
        self._validate_job_id(job_id)
        return await self.rpc(
            worker,
            {"action": "result", "job_id": job_id},
        )

    async def health(self, worker: Worker) -> dict[str, Any]:
        return await self.rpc(worker, {"action": "health"})

    async def upload(
        self,
        worker: Worker,
        job_id: str,
        input_paths: list[str],
    ) -> list[str]:
        self._validate_job_id(job_id)
        if len(input_paths) > 8:
            raise ValueError("a job accepts at most eight input files")

        input_root = self.settings.input_root.resolve(strict=True)
        selected: list[tuple[Path, str]] = []
        total_size = 0
        seen_names: set[str] = set()
        for raw_path in input_paths:
            path = Path(raw_path).resolve(strict=True)
            if not path.is_relative_to(input_root):
                raise ValueError(f"input path is outside the transfer root: {path}")
            file_stat = path.stat()
            if not stat.S_ISREG(file_stat.st_mode):
                raise ValueError(f"input is not a regular file: {path}")
            name = path.name
            if not _SAFE_NAME_RE.fullmatch(name):
                raise ValueError(f"unsafe input filename: {name}")
            if name in seen_names:
                raise ValueError(f"duplicate input filename: {name}")
            seen_names.add(name)
            total_size += file_stat.st_size
            if total_size > self.settings.max_input_bytes:
                raise ValueError("job inputs exceed the configured size limit")
            selected.append((path, name))

        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:") as archive:
            for path, name in selected:
                archive.add(path, arcname=name, recursive=False)
        result = await self._run(
            worker,
            f"barbarossa-worker upload {job_id}",
            input_data=buffer.getvalue(),
            encoding=None,
        )
        if result.exit_status != 0:
            detail = self._redactor.clean(self._text(result.stderr))
            raise RuntimeError(f"{worker} upload failed: {detail}")
        return [name for _, name in selected]

    async def download(
        self,
        worker: Worker,
        job_id: str,
    ) -> list[str]:
        self._validate_job_id(job_id)
        result = await self._run(
            worker,
            f"barbarossa-worker download {job_id}",
            input_data=b"",
            encoding=None,
        )
        if result.exit_status != 0:
            detail = self._redactor.clean(self._text(result.stderr))
            raise RuntimeError(f"{worker} download failed: {detail}")
        archive_bytes = result.stdout
        if isinstance(archive_bytes, str):
            archive_bytes = archive_bytes.encode()
        if len(archive_bytes) > self.settings.max_output_bytes:
            raise RuntimeError("worker archive exceeds the configured size limit")
        return self._extract_result(job_id, archive_bytes)

    def _extract_result(self, job_id: str, archive_bytes: bytes) -> list[str]:
        root = self.settings.result_root.resolve(strict=True)
        destination = root / job_id
        temporary = root / f".{job_id}.tmp"
        shutil.rmtree(temporary, ignore_errors=True)
        temporary.mkdir(mode=0o700)
        extracted: list[str] = []
        total_size = 0
        try:
            with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:*") as archive:
                members = archive.getmembers()
                if len(members) > 256:
                    raise ValueError("worker archive has too many members")
                for member in members:
                    path = PurePosixPath(member.name)
                    if (
                        not path.parts
                        or path.is_absolute()
                        or ".." in path.parts
                    ):
                        raise ValueError("worker archive contains an unsafe path")
                    if not (member.isfile() or member.isdir()):
                        raise ValueError("worker archive contains an unsafe member")
                    if path.parts[0] not in {
                        "outputs",
                        "stdout.log",
                        "stderr.log",
                        "result.json",
                    }:
                        raise ValueError("worker archive contains an unexpected member")
                    total_size += member.size
                    if total_size > self.settings.max_output_bytes:
                        raise ValueError("worker archive exceeds extracted size limit")
                archive.extractall(temporary, filter="data")
                extracted = [
                    str(destination / member.name)
                    for member in members
                    if member.isfile()
                ]
            if destination.exists():
                shutil.rmtree(destination)
            temporary.replace(destination)
            return extracted
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise

    @staticmethod
    def _validate_job_id(job_id: str) -> None:
        if not _JOB_ID_RE.fullmatch(job_id):
            raise ValueError(f"invalid job id: {job_id}")
