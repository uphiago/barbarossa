from pathlib import Path
from typing import Any

from barbarossa_router.models import (
    JobLogs,
    JobRequest,
    JobResult,
    JobStatus,
)
from barbarossa_router.scheduler import Scheduler
from barbarossa_router.ssh import SSHTransport
from barbarossa_router.store import JobStore


class RouterService:
    def __init__(
        self,
        store: JobStore,
        scheduler: Scheduler,
        transport: SSHTransport,
        result_root: Path,
    ) -> None:
        self.store = store
        self.scheduler = scheduler
        self.transport = transport
        self.result_root = result_root.resolve()

    async def start(self) -> None:
        await self.scheduler.start()

    async def close(self) -> None:
        await self.scheduler.close()
        await self.transport.close()

    async def submit(self, request: JobRequest) -> JobStatus:
        return await self.scheduler.submit(request)

    async def status(self, job_id: str) -> JobStatus:
        return await self.store.get(job_id)

    async def logs(self, job_id: str) -> JobLogs:
        job = await self.store.get(job_id)
        remote = await self.transport.logs(job.worker, job.job_id)
        return JobLogs(
            job_id=job.job_id,
            stdout=str(remote.get("stdout", "")),
            stderr=str(remote.get("stderr", "")),
            truncated=bool(remote.get("truncated", False)),
        )

    async def cancel(self, job_id: str) -> JobStatus:
        return await self.scheduler.cancel(job_id)

    async def result(self, job_id: str) -> JobResult:
        job = await self.store.get(job_id)
        if job.status not in {
            "succeeded",
            "failed",
            "cancelled",
            "interrupted",
        }:
            raise ValueError(f"job {job_id} is not finished")
        if job.status == "interrupted":
            return JobResult(job=job)

        paths = await self.transport.download(job.worker, job.job_id)
        destination = (self.result_root / job.job_id).resolve()
        artifacts: list[str] = []
        for raw_path in paths:
            path = Path(raw_path).resolve()
            if not path.is_relative_to(destination):
                raise RuntimeError("worker result escaped its job directory")
            artifacts.append(str(path))
        return JobResult(
            job=job,
            result_directory=str(destination),
            artifacts=artifacts,
        )

    async def health(self) -> dict[str, Any]:
        await self.store.initialize()
        return {
            "status": "ok",
            "workers": {
                "forge": await self.transport.health("forge"),
                "recon": await self.transport.health("recon"),
            },
        }
