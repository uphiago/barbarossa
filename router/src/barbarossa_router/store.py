import asyncio
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from barbarossa_router.models import JobRequest, JobStatus, Lane

TerminalState = Literal["succeeded", "failed", "cancelled", "interrupted"]

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _encode_crockford(value: int, length: int) -> str:
    output = ["0"] * length
    for index in range(length - 1, -1, -1):
        value, remainder = divmod(value, 32)
        output[index] = _CROCKFORD[remainder]
    return "".join(output)


def _new_ulid() -> str:
    timestamp = int(time.time() * 1000) & ((1 << 48) - 1)
    random_bits = int.from_bytes(os.urandom(10), "big")
    return _encode_crockford((timestamp << 80) | random_bits, 26)


def _job_kind(request: JobRequest) -> str:
    if request.capability.startswith("media.image."):
        return "image"
    if request.capability == "code.delegate":
        return "codex"
    if request.capability.startswith("network."):
        return "recon"
    return "runtime"


class JobStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = asyncio.Lock()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with self._lock:
            await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    queue_position INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL UNIQUE,
                    lane TEXT NOT NULL,
                    worker TEXT NOT NULL,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    status_json TEXT NOT NULL,
                    remote_pid INTEGER
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS jobs_lane_status_position
                ON jobs (lane, status, queue_position)
                """
            )

    async def create(self, request: JobRequest) -> JobStatus:
        async with self._lock:
            return await asyncio.to_thread(self._create_sync, request)

    def _create_sync(self, request: JobRequest) -> JobStatus:
        for _ in range(5):
            job_id = f"job_{_job_kind(request)}_{_new_ulid()}"
            status = JobStatus(
                job_id=job_id,
                capability=request.capability,
                worker=request.worker,
                lane=request.lane,
                route=request.route,
                status="queued",
            )
            try:
                with self._connect() as connection:
                    connection.execute(
                        """
                        INSERT INTO jobs (
                            job_id, lane, worker, status, request_json,
                            status_json, remote_pid
                        ) VALUES (?, ?, ?, ?, ?, ?, NULL)
                        """,
                        (
                            job_id,
                            request.lane,
                            request.worker,
                            status.status,
                            request.model_dump_json(),
                            status.model_dump_json(),
                        ),
                    )
                return status
            except sqlite3.IntegrityError:
                continue
        raise RuntimeError("could not allocate a unique job id")

    async def get(self, job_id: str) -> JobStatus:
        async with self._lock:
            return await asyncio.to_thread(self._get_sync, job_id)

    def _get_sync(self, job_id: str) -> JobStatus:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status_json FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"unknown job_id: {job_id}")
        return JobStatus.model_validate_json(row["status_json"])

    async def get_request(self, job_id: str) -> JobRequest:
        async with self._lock:
            return await asyncio.to_thread(self._get_request_sync, job_id)

    def _get_request_sync(self, job_id: str) -> JobRequest:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT request_json FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"unknown job_id: {job_id}")
        return JobRequest.model_validate_json(row["request_json"])

    async def next_queued(self, lane: Lane) -> JobStatus | None:
        async with self._lock:
            return await asyncio.to_thread(self._next_queued_sync, lane)

    def _next_queued_sync(self, lane: Lane) -> JobStatus | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT status_json FROM jobs
                WHERE lane = ? AND status = 'queued'
                ORDER BY queue_position
                LIMIT 1
                """,
                (lane,),
            ).fetchone()
        if row is None:
            return None
        return JobStatus.model_validate_json(row["status_json"])

    async def mark_running(
        self,
        job_id: str,
        remote_pid: int,
    ) -> JobStatus:
        async with self._lock:
            return await asyncio.to_thread(
                self._mark_running_sync,
                job_id,
                remote_pid,
            )

    def _mark_running_sync(
        self,
        job_id: str,
        remote_pid: int,
    ) -> JobStatus:
        current = self._get_sync(job_id)
        if current.status != "queued":
            raise ValueError(f"job {job_id} is not queued")
        updated = current.model_copy(
            update={
                "status": "running",
                "started_at": datetime.now(timezone.utc),
            }
        )
        self._update_sync(updated, remote_pid=remote_pid)
        return updated

    async def finish(
        self,
        job_id: str,
        *,
        status: TerminalState,
        exit_code: int | None,
        artifacts: list[str],
        error: str | None,
    ) -> JobStatus:
        async with self._lock:
            return await asyncio.to_thread(
                self._finish_sync,
                job_id,
                status,
                exit_code,
                artifacts,
                error,
            )

    def _finish_sync(
        self,
        job_id: str,
        status: TerminalState,
        exit_code: int | None,
        artifacts: list[str],
        error: str | None,
    ) -> JobStatus:
        current = self._get_sync(job_id)
        if current.status in {"succeeded", "failed", "cancelled", "interrupted"}:
            return current
        updated = current.model_copy(
            update={
                "status": status,
                "finished_at": datetime.now(timezone.utc),
                "exit_code": exit_code,
                "artifacts": artifacts,
                "error": error,
            }
        )
        self._update_sync(updated, remote_pid=None)
        return updated

    def _update_sync(
        self,
        status: JobStatus,
        *,
        remote_pid: int | None,
    ) -> None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status = ?, status_json = ?, remote_pid = ?
                WHERE job_id = ?
                """,
                (
                    status.status,
                    status.model_dump_json(),
                    remote_pid,
                    status.job_id,
                ),
            )
        if cursor.rowcount != 1:
            raise ValueError(f"unknown job_id: {status.job_id}")

    async def list_running(self) -> list[JobStatus]:
        return await self._list_by_status("running")

    async def list_all(self) -> list[JobStatus]:
        async with self._lock:
            return await asyncio.to_thread(self._list_all_sync)

    def _list_all_sync(self) -> list[JobStatus]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT status_json FROM jobs ORDER BY queue_position"
            ).fetchall()
        return [
            JobStatus.model_validate_json(row["status_json"])
            for row in rows
        ]

    async def _list_by_status(self, status: str) -> list[JobStatus]:
        async with self._lock:
            return await asyncio.to_thread(self._list_by_status_sync, status)

    def _list_by_status_sync(self, status: str) -> list[JobStatus]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT status_json FROM jobs
                WHERE status = ?
                ORDER BY queue_position
                """,
                (status,),
            ).fetchall()
        return [
            JobStatus.model_validate_json(row["status_json"])
            for row in rows
        ]
