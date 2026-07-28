from pathlib import Path
from typing import Any

import pytest

from barbarossa_router.models import JobStatus
from barbarossa_router.service import RouterService

SAFE_JOB_ID = "job_runtime_01J00000000000000000000000"


class FakeStore:
    async def get(self, job_id: str) -> JobStatus:
        return JobStatus(
            job_id=job_id,
            capability="runtime.execute",
            worker="forge",
            lane="runtime",
            route="direct",
            status="succeeded",
        )


class FakeTransport:
    def __init__(self, paths: list[str]) -> None:
        self.paths = paths

    async def download(self, worker: str, job_id: str) -> list[str]:
        return self.paths


class UnusedScheduler:
    pass


async def test_result_accepts_only_its_job_directory(
    tmp_path: Path,
) -> None:
    destination = tmp_path / SAFE_JOB_ID
    destination.mkdir()
    artifact = destination / "result.json"
    artifact.write_text("{}", encoding="utf-8")
    service = RouterService(
        FakeStore(),  # type: ignore[arg-type]
        UnusedScheduler(),  # type: ignore[arg-type]
        FakeTransport([str(artifact)]),  # type: ignore[arg-type]
        tmp_path,
    )

    result = await service.result(SAFE_JOB_ID)

    assert result.result_directory == str(destination)
    assert result.artifacts == [str(artifact)]


async def test_result_rejects_transport_path_escape(
    tmp_path: Path,
) -> None:
    outside = tmp_path.parent / "escaped-result"
    service = RouterService(
        FakeStore(),  # type: ignore[arg-type]
        UnusedScheduler(),  # type: ignore[arg-type]
        FakeTransport([str(outside)]),  # type: ignore[arg-type]
        tmp_path,
    )

    with pytest.raises(RuntimeError, match="escaped"):
        await service.result(SAFE_JOB_ID)
