import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ssh_key: Path
    known_hosts: Path
    state_db: Path
    input_root: Path
    result_root: Path
    forge_host: str = "forge"
    recon_host: str = "recon"
    max_log_bytes: int = Field(default=200_000, ge=1024, le=2_000_000)
    max_input_bytes: int = Field(
        default=32 * 1024 * 1024,
        ge=1024,
        le=128 * 1024 * 1024,
    )
    max_output_bytes: int = Field(
        default=64 * 1024 * 1024,
        ge=1024,
        le=256 * 1024 * 1024,
    )

    @classmethod
    def from_env(cls) -> "Settings":
        required = {
            "ssh_key": "BARBAROSSA_SSH_KEY",
            "known_hosts": "BARBAROSSA_KNOWN_HOSTS",
            "state_db": "BARBAROSSA_STATE_DB",
            "input_root": "BARBAROSSA_INPUT_ROOT",
            "result_root": "BARBAROSSA_RESULT_ROOT",
        }
        values: dict[str, object] = {}
        missing: list[str] = []
        for field_name, env_name in required.items():
            value = os.environ.get(env_name)
            if value:
                values[field_name] = Path(value)
            else:
                missing.append(env_name)
        if missing:
            raise ValueError(
                f"missing required environment variables: {', '.join(missing)}"
            )

        values.update(
            forge_host=os.environ.get("BARBAROSSA_FORGE_HOST", "forge"),
            recon_host=os.environ.get("BARBAROSSA_RECON_HOST", "recon"),
            max_log_bytes=int(
                os.environ.get("BARBAROSSA_MAX_LOG_BYTES", "200000")
            ),
            max_input_bytes=int(
                os.environ.get(
                    "BARBAROSSA_MAX_INPUT_BYTES",
                    str(32 * 1024 * 1024),
                )
            ),
            max_output_bytes=int(
                os.environ.get(
                    "BARBAROSSA_MAX_OUTPUT_BYTES",
                    str(64 * 1024 * 1024),
                )
            ),
        )
        return cls.model_validate(values)

    @model_validator(mode="after")
    def validate_paths(self) -> "Settings":
        path_fields = (
            "ssh_key",
            "known_hosts",
            "state_db",
            "input_root",
            "result_root",
        )
        for field_name in path_fields:
            path = getattr(self, field_name)
            if not path.is_absolute():
                raise ValueError(f"{field_name} must be an absolute path")

        input_root = self.input_root.resolve(strict=False)
        result_root = self.result_root.resolve(strict=False)
        if input_root == result_root:
            raise ValueError("input_root and result_root must differ")

        sensitive = (
            self.ssh_key.resolve(strict=False),
            self.known_hosts.resolve(strict=False),
            self.state_db.resolve(strict=False),
        )
        for root_name, root in (
            ("input_root", input_root),
            ("result_root", result_root),
        ):
            if any(path.is_relative_to(root) for path in sensitive):
                raise ValueError(f"{root_name} cannot contain router state")
        return self
