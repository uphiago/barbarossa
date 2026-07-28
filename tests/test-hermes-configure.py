import importlib.util
import os
from pathlib import Path
from types import ModuleType


def load_configure() -> ModuleType:
    path = (
        Path(__file__).parents[1]
        / "config"
        / "hermes"
        / "configure.py"
    )
    spec = importlib.util.spec_from_file_location("hermes_configure", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_configure_preserves_unrelated_state_and_is_private(
    tmp_path: Path,
) -> None:
    configure = load_configure()
    path = tmp_path / "config.yaml"
    path.write_text(
        "telegram:\n  allowed_users: '123'\nagent:\n  max_turns: 80\n",
        encoding="utf-8",
    )

    configure.configure(path)

    result = configure.yaml.safe_load(path.read_text(encoding="utf-8"))
    assert result["telegram"]["allowed_users"] == "123"
    assert result["agent"]["max_turns"] == 80
    assert result["delegation"]["max_concurrent_children"] == 3
    assert result["mcp_servers"]["barbarossa"][
        "supports_parallel_tool_calls"
    ] is True
    assert result["mcp_servers"]["barbarossa"]["env"][
        "BARBAROSSA_FORGE_HOST"
    ] == "forge"
    assert os.stat(path).st_mode & 0o777 == 0o600
