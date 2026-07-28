import asyncio

from barbarossa_router.models import JobRequest
from barbarossa_router.store import JobStore


async def test_store_round_trips_queued_job(
    store: JobStore,
    runtime_request: JobRequest,
) -> None:
    created = await store.create(runtime_request)
    loaded = await store.get(created.job_id)

    assert loaded == created
    assert await store.get_request(created.job_id) == runtime_request
    assert await store.next_queued("runtime") == created


async def test_store_preserves_fifo_order(
    store: JobStore,
    runtime_request: JobRequest,
) -> None:
    first = await store.create(runtime_request)
    second = await store.create(runtime_request)

    assert await store.next_queued("runtime") == first
    await store.mark_running(first.job_id, remote_pid=42)
    assert await store.next_queued("runtime") == second


async def test_claim_next_serializes_lane_across_store_instances(
    store: JobStore,
    runtime_request: JobRequest,
) -> None:
    first = await store.create(runtime_request)
    second = await store.create(runtime_request)
    competing_store = JobStore(store.path)

    claims = await asyncio.gather(
        store.claim_next("runtime"),
        competing_store.claim_next("runtime"),
    )

    assert [claim.job_id for claim in claims if claim is not None] == [
        first.job_id
    ]
    assert (await store.get(first.job_id)).status == "running"
    assert (await store.get(second.job_id)).status == "queued"


async def test_store_lists_running_jobs_for_remote_reconciliation(
    store: JobStore,
    runtime_request: JobRequest,
) -> None:
    created = await store.create(runtime_request)
    running = await store.mark_running(created.job_id, remote_pid=42)

    assert await store.list_running() == [running]


async def test_store_finishes_job_with_artifacts(
    store: JobStore,
    runtime_request: JobRequest,
) -> None:
    created = await store.create(runtime_request)
    await store.mark_running(created.job_id, remote_pid=42)

    finished = await store.finish(
        created.job_id,
        status="succeeded",
        exit_code=0,
        artifacts=["outputs/result.txt"],
        error=None,
    )

    assert finished.status == "succeeded"
    assert finished.exit_code == 0
    assert finished.finished_at is not None
    assert finished.artifacts == ["outputs/result.txt"]
