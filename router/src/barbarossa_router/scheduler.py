import asyncio
from datetime import datetime, timezone
from typing import Any, Protocol

from barbarossa_router.models import JobRequest, JobStatus, Lane, Worker
from barbarossa_router.store import JobStore, TerminalState

TERMINAL_STATES = {"succeeded", "failed", "cancelled", "interrupted"}


class WorkerTransport(Protocol):
    async def start(
        self,
        worker: Worker,
        job_id: str,
        request: JobRequest,
    ) -> dict[str, Any]: ...

    async def status(
        self,
        worker: Worker,
        job_id: str,
    ) -> dict[str, Any]: ...

    async def cancel(
        self,
        worker: Worker,
        job_id: str,
    ) -> dict[str, Any]: ...


class Scheduler:
    def __init__(
        self,
        store: JobStore,
        transport: WorkerTransport,
        *,
        poll_interval: float = 2.0,
    ) -> None:
        self.store = store
        self.transport = transport
        self.poll_interval = poll_interval
        self._active_jobs: dict[Lane, str] = {}
        self._tick_lock = asyncio.Lock()
        self._loop_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        await self.store.initialize()
        await self.reconcile()
        if self._loop_task is None:
            self._loop_task = asyncio.create_task(
                self._run_loop(),
                name="barbarossa-scheduler",
            )

    async def close(self) -> None:
        if self._loop_task is None:
            return
        self._loop_task.cancel()
        try:
            await self._loop_task
        except asyncio.CancelledError:
            pass
        self._loop_task = None

    async def _run_loop(self) -> None:
        while True:
            await self.poll_once()
            await self.tick()
            await asyncio.sleep(self.poll_interval)

    async def submit(self, request: JobRequest) -> JobStatus:
        return await self.store.create(request)

    async def tick(self) -> None:
        async with self._tick_lock:
            for lane in ("runtime", "codex", "recon"):
                typed_lane: Lane = lane
                claimed = await self.store.claim_next(typed_lane)
                if claimed is None:
                    continue
                self._active_jobs[typed_lane] = claimed.job_id
                request = await self.store.get_request(claimed.job_id)
                try:
                    await self.transport.start(
                        claimed.worker,
                        claimed.job_id,
                        request,
                    )
                except Exception as exc:
                    await self.store.finish(
                        claimed.job_id,
                        status="failed",
                        exit_code=None,
                        artifacts=[],
                        error=f"worker start failed: {exc}",
                    )
                    self._release_lane(typed_lane, claimed.job_id)

    async def reconcile(self) -> None:
        for job in await self.store.list_running():
            try:
                remote = await self.transport.status(job.worker, job.job_id)
            except Exception:
                await self._reserve_lane(job)
                continue

            remote_status = remote.get("status")
            if remote_status == "running":
                await self._reserve_lane(job)
                continue
            if remote_status in TERMINAL_STATES:
                await self._finish_from_remote(job, remote)
                continue
            await self.store.finish(
                job.job_id,
                status="interrupted",
                exit_code=None,
                artifacts=[],
                error="worker could not confirm running job",
            )

    async def _reserve_lane(self, job: JobStatus) -> None:
        self._active_jobs[job.lane] = job.job_id

    async def poll_once(self) -> None:
        for job in await self.store.list_running():
            request = await self.store.get_request(job.job_id)
            if self._is_timed_out(job, request):
                try:
                    await self.cancel(job.job_id)
                except Exception:
                    continue
                continue
            try:
                remote = await self.transport.status(job.worker, job.job_id)
            except Exception:
                continue
            if remote.get("status") in TERMINAL_STATES:
                await self._finish_from_remote(job, remote)

    def _is_timed_out(
        self,
        job: JobStatus,
        request: JobRequest,
    ) -> bool:
        if job.started_at is None:
            return False
        if request.timeout_seconds is None:
            return False
        elapsed = datetime.now(timezone.utc) - job.started_at
        return elapsed.total_seconds() >= request.timeout_seconds

    async def _finish_from_remote(
        self,
        job: JobStatus,
        remote: dict[str, Any],
    ) -> JobStatus:
        status = remote["status"]
        if status not in TERMINAL_STATES:
            raise ValueError(f"worker returned non-terminal status: {status}")
        finished = await self.store.finish(
            job.job_id,
            status=status,
            exit_code=remote.get("exit_code"),
            artifacts=list(remote.get("artifacts") or []),
            error=remote.get("error"),
        )
        self._release_lane(job.lane, job.job_id)
        return finished

    async def cancel(self, job_id: str) -> JobStatus:
        job = await self.store.get(job_id)
        if job.status == "queued":
            return await self.store.finish(
                job.job_id,
                status="cancelled",
                exit_code=None,
                artifacts=[],
                error=None,
            )
        if job.status != "running":
            return job
        remote = await self.transport.cancel(job.worker, job.job_id)
        if remote.get("status") not in TERMINAL_STATES:
            raise ValueError("worker did not confirm cancellation")
        return await self._finish_from_remote(job, remote)

    def lane_is_active(self, lane: Lane) -> bool:
        return lane in self._active_jobs

    def _release_lane(self, lane: Lane, job_id: str) -> None:
        if self._active_jobs.get(lane) != job_id:
            return
        del self._active_jobs[lane]
