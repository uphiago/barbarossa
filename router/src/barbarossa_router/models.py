from datetime import datetime, timezone
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, model_validator

Capability = Literal[
    "runtime.execute",
    "code.delegate",
    "media.file.inspect",
    "media.image.inspect",
    "media.image.generate",
    "media.image.edit",
    "network.inspect",
    "network.fetch",
    "network.tor",
]
JobState = Literal[
    "queued",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    "interrupted",
]
Lane = Literal["runtime", "codex", "recon"]
Route = Literal["direct", "tor"]
Worker = Literal["forge", "recon"]

JOB_ID_PATTERN = (
    r"^job_(runtime|codex|image|recon)_[0-9A-HJKMNP-TV-Z]{26}$"
)

CAPABILITY_POLICY: dict[Capability, tuple[Worker, Lane, int]] = {
    "runtime.execute": ("forge", "runtime", 900),
    "code.delegate": ("forge", "codex", 2700),
    "media.file.inspect": ("forge", "runtime", 900),
    "media.image.inspect": ("forge", "codex", 1200),
    "media.image.generate": ("forge", "codex", 1200),
    "media.image.edit": ("forge", "codex", 1200),
    "network.inspect": ("recon", "recon", 1200),
    "network.fetch": ("recon", "recon", 1200),
    "network.tor": ("recon", "recon", 1200),
}


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: Capability
    command: str | None = Field(default=None, max_length=32_768)
    prompt: str | None = Field(default=None, max_length=65_536)
    url: AnyHttpUrl | None = None
    route: Route = "direct"
    timeout_seconds: int | None = Field(default=None, ge=1, le=7200)
    input_paths: list[str] = Field(default_factory=list, max_length=8)

    worker: Worker = "forge"
    lane: Lane = "runtime"

    @model_validator(mode="after")
    def apply_policy(self) -> "JobRequest":
        worker, lane, default_timeout = CAPABILITY_POLICY[self.capability]
        self.worker = worker
        self.lane = lane
        self.timeout_seconds = self.timeout_seconds or default_timeout

        if self.capability == "network.tor":
            self.route = "tor"
        elif self.route == "tor":
            raise ValueError("Tor route requires network.tor")

        if (
            self.capability in {"runtime.execute", "network.inspect", "network.tor"}
            and not self.command
        ):
            raise ValueError("command is required for this capability")
        if (
            self.capability.startswith(("code.", "media.image."))
            and not self.prompt
        ):
            raise ValueError("prompt is required for this capability")
        if self.capability == "network.fetch" and self.url is None:
            raise ValueError("url is required for network.fetch")

        single_input_capabilities = {
            "media.file.inspect",
            "media.image.inspect",
            "media.image.edit",
        }
        if (
            self.capability in single_input_capabilities
            and len(self.input_paths) != 1
        ):
            raise ValueError("this capability requires exactly one input file")
        if self.capability == "media.image.generate" and self.input_paths:
            raise ValueError("media.image.generate does not accept an input file")
        return self


class JobStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(pattern=JOB_ID_PATTERN)
    capability: Capability
    worker: Worker
    lane: Lane
    route: Route
    status: JobState
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    started_at: datetime | None = None
    finished_at: datetime | None = None
    exit_code: int | None = None
    artifacts: list[str] = Field(default_factory=list)
    error: str | None = None


class JobLogs(BaseModel):
    job_id: str = Field(pattern=JOB_ID_PATTERN)
    stdout: str
    stderr: str
    truncated: bool = False


class JobResult(BaseModel):
    job: JobStatus
    result_directory: str | None = None
    artifacts: list[str] = Field(default_factory=list)
