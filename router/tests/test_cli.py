from pathlib import Path

from barbarossa_router.cli import build_service, parser
from barbarossa_router.config import Settings


def test_operator_inspection_commands_require_job_id() -> None:
    command_parser = parser()

    for command in ("status", "logs", "result"):
        parsed = command_parser.parse_args([command, "job_runtime_01ARZ3NDEKTSV4RRFFQ69G5FAV"])
        assert parsed.operator_command == command
        assert parsed.job_id == "job_runtime_01ARZ3NDEKTSV4RRFFQ69G5FAV"


def test_build_service_prepares_private_state_directories(
    tmp_path: Path,
) -> None:
    settings = Settings(
        ssh_key=tmp_path / "secrets" / "key",
        known_hosts=tmp_path / "secrets" / "known_hosts",
        state_db=tmp_path / "state" / "jobs.sqlite3",
        input_root=tmp_path / "inputs",
        result_root=tmp_path / "results",
    )

    build_service(settings)

    assert settings.state_db.parent.is_dir()
    assert settings.input_root.is_dir()
    assert settings.result_root.is_dir()
