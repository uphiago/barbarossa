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


def set_required_model(
    monkeypatch,
    *,
    provider: str = "deepseek",
    model: str = "deepseek-v4-flash",
) -> None:
    monkeypatch.setenv("HERMES_MODEL_PROVIDER", provider)
    monkeypatch.setenv("HERMES_MODEL_NAME", model)


def test_configure_preserves_unrelated_state_and_is_private(
    tmp_path: Path,
    monkeypatch,
) -> None:
    configure = load_configure()
    set_required_model(monkeypatch)
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
    assert result["mcp_servers"]["barbarossa"]["env"][
        "BARBAROSSA_SSH_KEY"
    ] == "/run/barbarossa-secrets/worker_key"
    assert os.stat(path).st_mode & 0o777 == 0o600


def test_configure_replaces_stale_provider_state_from_environment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    configure = load_configure()
    set_required_model(
        monkeypatch,
        provider="openrouter",
        model="anthropic/claude-sonnet-4.6",
    )
    path = tmp_path / "config.yaml"
    path.write_text(
        "model:\n"
        "  provider: deepseek\n"
        "  name: deepseek-v4-flash\n"
        "  default: deepseek-v4-flash\n"
        "  base_url: https://api.deepseek.com/v1\n"
        "  api_key: stale-provider-key\n"
        "  api_mode: responses\n",
        encoding="utf-8",
    )

    configure.configure(path)

    result = configure.yaml.safe_load(path.read_text(encoding="utf-8"))
    assert result["model"] == {
        "provider": "openrouter",
        "name": "anthropic/claude-sonnet-4.6",
        "default": "anthropic/claude-sonnet-4.6",
    }
    assert "provider" not in result["delegation"]
    assert "model" not in result["delegation"]


def test_configure_applies_explicit_model_and_delegation_overrides(
    tmp_path: Path,
    monkeypatch,
) -> None:
    configure = load_configure()
    set_required_model(monkeypatch, provider="custom", model="qwen3-coder")
    monkeypatch.setenv(
        "HERMES_MODEL_BASE_URL",
        "http://inference.internal/v1",
    )
    monkeypatch.setenv("HERMES_MODEL_API_MODE", "chat_completions")
    monkeypatch.setenv("HERMES_REASONING_EFFORT", "high")
    monkeypatch.setenv("HERMES_DELEGATION_PROVIDER", "openrouter")
    monkeypatch.setenv("HERMES_DELEGATION_MODEL", "google/gemini-flash")
    monkeypatch.setenv("HERMES_MAX_CONCURRENT_CHILDREN", "7")
    monkeypatch.setenv("HERMES_MAX_SPAWN_DEPTH", "2")
    monkeypatch.setenv("HERMES_ORCHESTRATOR_ENABLED", "false")
    path = tmp_path / "config.yaml"

    configure.configure(path)

    result = configure.yaml.safe_load(path.read_text(encoding="utf-8"))
    assert result["model"] == {
        "provider": "custom",
        "name": "qwen3-coder",
        "default": "qwen3-coder",
        "base_url": "http://inference.internal/v1",
        "api_mode": "chat_completions",
    }
    assert result["agent"]["reasoning_effort"] == "high"
    assert result["delegation"]["provider"] == "openrouter"
    assert result["delegation"]["model"] == "google/gemini-flash"
    assert result["delegation"]["max_concurrent_children"] == 7
    assert result["delegation"]["max_spawn_depth"] == 2
    assert result["delegation"]["orchestrator_enabled"] is False


def test_configure_rejects_invalid_numeric_environment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    configure = load_configure()
    set_required_model(monkeypatch)
    monkeypatch.setenv("HERMES_MAX_CONCURRENT_CHILDREN", "many")

    try:
        configure.configure(tmp_path / "config.yaml")
    except ValueError as error:
        assert "HERMES_MAX_CONCURRENT_CHILDREN" in str(error)
    else:
        raise AssertionError("invalid concurrency was accepted")


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


def test_agent_context_requires_confirmation_before_model_fallback() -> None:
    context = Path(__file__).parents[1] / "AGENTS.md"

    text = context.read_text(encoding="utf-8")

    assert "requested model" in text
    assert "ask for confirmation" in text
