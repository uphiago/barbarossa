from contextlib import asynccontextmanager
from typing import AsyncIterator

from mcp.server import MCPServer

from barbarossa_router.models import JobLogs, JobRequest, JobResult, JobStatus
from barbarossa_router.service import RouterService


def create_server(service: RouterService) -> MCPServer:
    @asynccontextmanager
    async def lifespan(_: MCPServer) -> AsyncIterator[None]:
        await service.start()
        try:
            yield None
        finally:
            await service.close()

    mcp = MCPServer(
        "barbarossa",
        version="1.0.0",
        instructions=(
            "Dispatch isolated jobs to Forge or Recon. Start a job, then use "
            "job_status, job_logs, job_result, or job_cancel with its job_id. "
            "Tor is used only by the explicit network_tor tool."
        ),
        lifespan=lifespan,
    )

    @mcp.tool()
    async def runtime_execute(
        command: str,
        timeout_seconds: int = 900,
    ) -> JobStatus:
        """Queue an isolated shell job in the Forge runtime lane."""
        return await service.submit(
            JobRequest(
                capability="runtime.execute",
                command=command,
                timeout_seconds=timeout_seconds,
            )
        )

    @mcp.tool()
    async def code_delegate(
        prompt: str,
        input_paths: list[str] | None = None,
        timeout_seconds: int = 2700,
        codex_profile: str | None = None,
    ) -> JobStatus:
        """Queue an engineering job for the configured Codex profile."""
        return await service.submit(
            JobRequest(
                capability="code.delegate",
                prompt=prompt,
                input_paths=input_paths or [],
                timeout_seconds=timeout_seconds,
                codex_profile=codex_profile,
            )
        )

    @mcp.tool()
    async def media_file_inspect(
        input_path: str,
        timeout_seconds: int = 900,
    ) -> JobStatus:
        """Inspect a staged file's type and MIME metadata in Forge."""
        return await service.submit(
            JobRequest(
                capability="media.file.inspect",
                input_paths=[input_path],
                timeout_seconds=timeout_seconds,
            )
        )

    @mcp.tool()
    async def media_image_inspect(
        input_path: str,
        prompt: str,
        timeout_seconds: int = 1200,
        codex_profile: str | None = None,
    ) -> JobStatus:
        """Inspect a staged image with Codex vision in Forge."""
        return await service.submit(
            JobRequest(
                capability="media.image.inspect",
                input_paths=[input_path],
                prompt=prompt,
                timeout_seconds=timeout_seconds,
                codex_profile=codex_profile,
            )
        )

    @mcp.tool()
    async def media_image_generate(
        prompt: str,
        timeout_seconds: int = 1200,
        codex_profile: str | None = None,
    ) -> JobStatus:
        """Generate an image through Codex and its image tool in Forge."""
        return await service.submit(
            JobRequest(
                capability="media.image.generate",
                prompt=prompt,
                timeout_seconds=timeout_seconds,
                codex_profile=codex_profile,
            )
        )

    @mcp.tool()
    async def media_image_edit(
        input_path: str,
        prompt: str,
        timeout_seconds: int = 1200,
        codex_profile: str | None = None,
    ) -> JobStatus:
        """Edit a staged image through Codex in Forge."""
        return await service.submit(
            JobRequest(
                capability="media.image.edit",
                input_paths=[input_path],
                prompt=prompt,
                timeout_seconds=timeout_seconds,
                codex_profile=codex_profile,
            )
        )

    @mcp.tool()
    async def network_inspect(
        command: str,
        timeout_seconds: int = 1200,
    ) -> JobStatus:
        """Queue an authorized direct-network inspection in Recon."""
        return await service.submit(
            JobRequest(
                capability="network.inspect",
                command=command,
                timeout_seconds=timeout_seconds,
            )
        )

    @mcp.tool()
    async def network_fetch(
        url: str,
        timeout_seconds: int = 1200,
    ) -> JobStatus:
        """Fetch one HTTP(S) URL directly from Recon."""
        return await service.submit(
            JobRequest(
                capability="network.fetch",
                url=url,
                timeout_seconds=timeout_seconds,
            )
        )

    @mcp.tool()
    async def network_tor(
        command: str,
        timeout_seconds: int = 1200,
    ) -> JobStatus:
        """Queue an authorized Recon command explicitly routed through Tor."""
        return await service.submit(
            JobRequest(
                capability="network.tor",
                command=command,
                timeout_seconds=timeout_seconds,
            )
        )

    @mcp.tool()
    async def gmail_send(
        to: str,
        subject: str,
        body: str,
        timeout_seconds: int = 120,
    ) -> JobStatus:
        """Send an email from hey@hiago.sh via Gmail SMTP through Forge."""
        return await service.submit(
            JobRequest(
                capability="mail.send",
                to=to,
                subject=subject,
                body=body,
                timeout_seconds=timeout_seconds,
            )
        )

    @mcp.tool()
    async def gmail_read(
        mailbox: str = "INBOX",
        limit: int = 10,
        query: str = "ALL",
        timeout_seconds: int = 120,
    ) -> JobStatus:
        """Read recent emails from hey@hiago.sh via Gmail IMAP through Forge."""
        return await service.submit(
            JobRequest(
                capability="mail.read",
                mailbox=mailbox,
                limit=limit,
                query=query,
                timeout_seconds=timeout_seconds,
            )
        )

    @mcp.tool()
    async def job_status(job_id: str) -> JobStatus:
        """Return the durable status of a Barbarossa job."""
        return await service.status(job_id)

    @mcp.tool()
    async def job_logs(job_id: str) -> JobLogs:
        """Return bounded, redacted stdout and stderr for a job."""
        return await service.logs(job_id)

    @mcp.tool()
    async def job_cancel(job_id: str) -> JobStatus:
        """Cancel a queued or running job."""
        return await service.cancel(job_id)

    @mcp.tool()
    async def job_result(job_id: str) -> JobResult:
        """Download and safely extract a completed job's result archive."""
        return await service.result(job_id)

    return mcp
