from typing import Any

import pytest
from mcp import Client

from barbarossa_router.models import JobLogs, JobResult, JobStatus
from barbarossa_router.server import create_server

SAFE_JOB_ID = "job_runtime_01J00000000000000000000000"


class FakeService:
    def __init__(self) -> None:
        self.started = False
        self.closed = False
        self.requests: list[Any] = []

    async def start(self) -> None:
        self.started = True

    async def close(self) -> None:
        self.closed = True

    async def submit(self, request: Any) -> JobStatus:
        self.requests.append(request)
        return JobStatus(
            job_id=SAFE_JOB_ID.replace("runtime", request.lane),
            capability=request.capability,
            worker=request.worker,
            lane=request.lane,
            route=request.route,
            status="queued",
        )

    async def status(self, job_id: str) -> JobStatus:
        return JobStatus(
            job_id=job_id,
            capability="runtime.execute",
            worker="forge",
            lane="runtime",
            route="direct",
            status="running",
        )

    async def logs(self, job_id: str) -> JobLogs:
        return JobLogs(job_id=job_id, stdout="ok", stderr="")

    async def cancel(self, job_id: str) -> JobStatus:
        status = await self.status(job_id)
        return status.model_copy(update={"status": "cancelled"})

    async def result(self, job_id: str) -> JobResult:
        status = await self.status(job_id)
        return JobResult(
            job=status.model_copy(update={"status": "succeeded"}),
            result_directory=f"/results/{job_id}",
        )


@pytest.fixture
async def service() -> FakeService:
    return FakeService()


async def test_runtime_execute_returns_structured_job(
    service: FakeService,
) -> None:
    async with Client(
        create_server(service),
        raise_exceptions=True,
    ) as client:
        result = await client.call_tool(
            "runtime_execute",
            {"command": "printf ok", "timeout_seconds": 30},
        )

    assert result.is_error is False
    assert result.structured_content["status"] == "queued"
    assert result.structured_content["worker"] == "forge"
    assert service.requests[0].command == "printf ok"


async def test_code_delegate_passes_an_approved_codex_profile(
    service: FakeService,
) -> None:
    async with Client(
        create_server(service),
        raise_exceptions=True,
    ) as client:
        result = await client.call_tool(
            "code_delegate",
            {
                "prompt": "Review this change",
                "codex_profile": "deep",
            },
        )

    assert result.is_error is False
    assert service.requests[-1].codex_profile == "deep"


async def test_tor_is_explicit_and_routes_to_recon(
    service: FakeService,
) -> None:
    async with Client(
        create_server(service),
        raise_exceptions=True,
    ) as client:
        result = await client.call_tool(
            "network_tor",
            {"command": "curl https://example.com", "timeout_seconds": 30},
        )

    assert result.is_error is False
    assert result.structured_content["worker"] == "recon"
    assert service.requests[-1].route == "tor"


async def test_invalid_command_is_a_model_visible_tool_error(
    service: FakeService,
) -> None:
    async with Client(
        create_server(service),
        raise_exceptions=True,
    ) as client:
        result = await client.call_tool(
            "network_tor",
            {"command": "", "timeout_seconds": 30},
        )
    assert result.is_error is True


async def test_job_tools_return_structured_models(
    service: FakeService,
) -> None:
    async with Client(
        create_server(service),
        raise_exceptions=True,
    ) as client:
        status = await client.call_tool("job_status", {"job_id": SAFE_JOB_ID})
        logs = await client.call_tool("job_logs", {"job_id": SAFE_JOB_ID})
        result = await client.call_tool("job_result", {"job_id": SAFE_JOB_ID})

    assert status.structured_content["status"] == "running"
    assert logs.structured_content["stdout"] == "ok"
    assert result.structured_content["job"]["status"] == "succeeded"


async def test_lifespan_starts_and_closes_service(
    service: FakeService,
) -> None:
    server = create_server(service)
    async with Client(server, raise_exceptions=True):
        assert service.started is True
    assert service.closed is True


async def test_server_exposes_only_approved_tools(
    service: FakeService,
) -> None:
    async with Client(
        create_server(service),
        raise_exceptions=True,
    ) as client:
        tools = await client.list_tools()

    assert {tool.name for tool in tools.tools} == {
        "runtime_execute",
        "code_delegate",
        "media_file_inspect",
        "media_image_inspect",
        "media_image_generate",
        "media_image_edit",
        "network_inspect",
        "network_fetch",
        "network_tor",
        "job_status",
        "job_logs",
        "job_cancel",
        "job_result",
    }
