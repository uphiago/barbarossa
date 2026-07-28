from collections import defaultdict
from typing import Any

from barbarossa_router.models import JobRequest, JobStatus
from barbarossa_router.scheduler import Scheduler
from barbarossa_router.store import JobStore


class FakeTransport:
    def __init__(self) -> None:
        self.started_lanes: list[str] = []
        self.statuses: dict[str, dict[str, Any]] = {}
        self.cancelled: list[str] = []
        self._pid = 100

    async def start(
        self,
        worker: str,
        job_id: str,
        request: JobRequest,
    ) -> dict[str, Any]:
        self.started_lanes.append(request.lane)
        self._pid += 1
        self.statuses[job_id] = {
            "status": "running",
            "remote_pid": self._pid,
        }
        return self.statuses[job_id]

    async def status(self, worker: str, job_id: str) -> dict[str, Any]:
        return self.statuses.get(job_id, {"status": "unknown"})

    async def cancel(self, worker: str, job_id: str) -> dict[str, Any]:
        self.cancelled.append(job_id)
        self.statuses[job_id] = {
            "status": "cancelled",
            "exit_code": None,
            "artifacts": [],
            "error": None,
        }
        return self.statuses[job_id]


async def make_scheduler(store: JobStore) -> tuple[Scheduler, FakeTransport]:
    transport = FakeTransport()
    scheduler = Scheduler(store, transport, poll_interval=0.01)
    return scheduler, transport


async def test_one_job_per_lane_and_runtime_parallel_with_codex(
    store: JobStore,
    runtime_request: JobRequest,
    codex_request: JobRequest,
) -> None:
    scheduler, transport = await make_scheduler(store)
    await scheduler.submit(runtime_request)
    await scheduler.submit(runtime_request)
    await scheduler.submit(codex_request)

    await scheduler.tick()

    assert transport.started_lanes == ["runtime", "codex"]
    statuses = defaultdict(int)
    for job in await store.list_all():
        statuses[job.status] += 1
    assert statuses == {"running": 2, "queued": 1}


async def test_terminal_poll_releases_lane_for_next_job(
    store: JobStore,
    runtime_request: JobRequest,
) -> None:
    scheduler, transport = await make_scheduler(store)
    first = await scheduler.submit(runtime_request)
    second = await scheduler.submit(runtime_request)
    await scheduler.tick()
    transport.statuses[first.job_id] = {
        "status": "succeeded",
        "exit_code": 0,
        "artifacts": [],
        "error": None,
    }

    await scheduler.poll_once()
    await scheduler.tick()

    assert (await store.get(first.job_id)).status == "succeeded"
    assert (await store.get(second.job_id)).status == "running"


async def test_cross_process_polling_does_not_deadlock_lane(
    store: JobStore,
    runtime_request: JobRequest,
) -> None:
    transport = FakeTransport()
    other_store = JobStore(store.path)
    first_scheduler = Scheduler(store, transport)
    second_scheduler = Scheduler(other_store, transport)
    first = await first_scheduler.submit(runtime_request)
    second = await first_scheduler.submit(runtime_request)

    await first_scheduler.tick()
    transport.statuses[first.job_id] = {
        "status": "succeeded",
        "exit_code": 0,
        "artifacts": [],
        "error": None,
    }
    await second_scheduler.poll_once()
    await second_scheduler.tick()
    transport.statuses[second.job_id] = {
        "status": "succeeded",
        "exit_code": 0,
        "artifacts": [],
        "error": None,
    }
    await first_scheduler.poll_once()
    third = await first_scheduler.submit(runtime_request)

    await first_scheduler.tick()
    await second_scheduler.tick()

    assert (await store.get(third.job_id)).status == "running"


async def test_reconcile_keeps_confirmed_remote_process_running(
    store: JobStore,
    runtime_request: JobRequest,
) -> None:
    scheduler, transport = await make_scheduler(store)
    created = await store.create(runtime_request)
    await store.mark_running(created.job_id, remote_pid=42)
    transport.statuses[created.job_id] = {
        "status": "running",
        "remote_pid": 42,
    }

    await scheduler.reconcile()

    assert (await store.get(created.job_id)).status == "running"
    assert scheduler.lane_is_active("runtime")


async def test_reconcile_interrupts_unconfirmed_job(
    store: JobStore,
    runtime_request: JobRequest,
) -> None:
    scheduler, _ = await make_scheduler(store)
    created = await store.create(runtime_request)
    await store.mark_running(created.job_id, remote_pid=42)

    await scheduler.reconcile()

    assert (await store.get(created.job_id)).status == "interrupted"


async def test_cancel_running_job_releases_lane(
    store: JobStore,
    runtime_request: JobRequest,
) -> None:
    scheduler, transport = await make_scheduler(store)
    created = await scheduler.submit(runtime_request)
    await scheduler.tick()

    cancelled = await scheduler.cancel(created.job_id)

    assert cancelled.status == "cancelled"
    assert transport.cancelled == [created.job_id]
    assert not scheduler.lane_is_active("runtime")
