from pathlib import Path

import pytest

from barbarossa_router.models import JobRequest
from barbarossa_router.store import JobStore


@pytest.fixture
async def store(tmp_path: Path) -> JobStore:
    instance = JobStore(tmp_path / "jobs.sqlite3")
    await instance.initialize()
    return instance


@pytest.fixture
def runtime_request() -> JobRequest:
    return JobRequest(
        capability="runtime.execute",
        command="printf runtime",
    )


@pytest.fixture
def codex_request() -> JobRequest:
    return JobRequest(
        capability="code.delegate",
        prompt="Review the repository",
    )
