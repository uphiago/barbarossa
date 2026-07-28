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
        "telegram:\n"
        "  allowed_users: '123'\n"
        "agent:\n"
        "  max_turns: 80\n"
        "  disabled_toolsets:\n"
        "    - memory\n",
        encoding="utf-8",
    )

    configure.configure(path)

    result = configure.yaml.safe_load(path.read_text(encoding="utf-8"))
    assert result["telegram"]["allowed_users"] == "123"
    assert result["agent"]["max_turns"] == 80
    assert result["agent"]["image_input_mode"] == "text"
    assert result["agent"]["disabled_toolsets"] == ["memory", "vision"]
    assert result["delegation"]["max_concurrent_children"] == 3
    assert result["mcp_servers"]["barbarossa"][
        "supports_parallel_tool_calls"
    ] is True
    assert result["mcp_servers"]["barbarossa"]["env"][
        "BARBAROSSA_FORGE_HOST"
    ] == "forge"
    assert os.stat(path).st_mode & 0o777 == 0o600


def test_configure_replaces_stale_openrouter_model_state(
    tmp_path: Path,
) -> None:
    configure = load_configure()
    path = tmp_path / "config.yaml"
    path.write_text(
        "model:\n"
        "  provider: openrouter\n"
        "  name: deepseek/deepseek-v4-flash\n"
        "  default: deepseek/deepseek-v4-flash\n"
        "  base_url: https://openrouter.ai/api/v1\n"
        "  api_key: stale-provider-key\n"
        "  api_mode: responses\n",
        encoding="utf-8",
    )

    configure.configure(path)

    result = configure.yaml.safe_load(path.read_text(encoding="utf-8"))
    assert result["model"] == {
        "provider": "deepseek",
        "name": "deepseek-v4-flash",
        "default": "deepseek-v4-flash",
        "base_url": "https://api.deepseek.com/v1",
    }
    assert result["delegation"]["provider"] == "deepseek"
    assert result["delegation"]["model"] == "deepseek-v4-flash"


def test_install_context_replaces_only_barbarossa_assets(
    tmp_path: Path,
) -> None:
    configure = load_configure()
    source = tmp_path / "source"
    data = tmp_path / "data"
    (source / "skills" / "barbarossa-routing").mkdir(parents=True)
    (source / "skills" / "barbarossa-routing" / "SKILL.md").write_text(
        "new routing",
        encoding="utf-8",
    )
    (source / "AGENTS.md").write_text("agent context", encoding="utf-8")
    (data / "skills" / "bundled").mkdir(parents=True)
    (data / "skills" / "bundled" / "SKILL.md").write_text(
        "keep",
        encoding="utf-8",
    )

    configure.install_context(source, data)

    assert (data / "AGENTS.md").read_text(encoding="utf-8") == "agent context"
    assert os.stat(data / "AGENTS.md").st_mode & 0o777 == 0o600
    assert (
        data / "skills" / "barbarossa-routing" / "SKILL.md"
    ).read_text(encoding="utf-8") == "new routing"
    assert (
        data / "skills" / "bundled" / "SKILL.md"
    ).read_text(encoding="utf-8") == "keep"
