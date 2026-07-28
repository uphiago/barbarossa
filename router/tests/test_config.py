from pathlib import Path

import pytest
from pydantic import ValidationError

from barbarossa_router.config import Settings


def settings_values(tmp_path: Path) -> dict[str, object]:
    return {
        "ssh_key": tmp_path / "secrets" / "worker_key",
        "known_hosts": tmp_path / "secrets" / "known_hosts",
        "state_db": tmp_path / "state" / "jobs.sqlite3",
        "input_root": tmp_path / "transfer",
        "result_root": tmp_path / "results",
    }


def test_settings_require_absolute_paths(tmp_path: Path) -> None:
    values = settings_values(tmp_path)
    values["ssh_key"] = Path("worker_key")

    with pytest.raises(ValidationError, match="absolute"):
        Settings.model_validate(values)


def test_transfer_root_cannot_contain_router_state(tmp_path: Path) -> None:
    values = settings_values(tmp_path)
    values["input_root"] = tmp_path

    with pytest.raises(ValidationError, match="cannot contain router state"):
        Settings.model_validate(values)
