#!/usr/bin/env python3
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import yaml

CONFIG_PATH = Path("/opt/data/config.yaml")
CONTEXT_ROOT = Path("/opt/barbarossa/context")
DATA_ROOT = Path("/opt/data")
REASONING_EFFORTS = {
    "none",
    "minimal",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
    "ultra",
}
API_MODES = {
    "chat_completions",
    "codex_responses",
    "anthropic_messages",
}


def merge(target: dict[str, Any], updates: dict[str, Any]) -> None:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            merge(target[key], value)
        else:
            target[key] = value


def environment_value(name: str, *, required: bool = False) -> str:
    value = os.environ.get(name, "").strip()
    if required and not value:
        raise ValueError(f"{name} is required")
    if any(character in value for character in ("\n", "\r", "\0")):
        raise ValueError(f"{name} contains an invalid character")
    return value


def environment_integer(
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int | None = None,
) -> int:
    raw = environment_value(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"{name} is outside the supported range")
    return value


def environment_boolean(name: str, default: bool) -> bool:
    raw = environment_value(name).lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def desired_config() -> dict[str, Any]:
    provider = environment_value("HERMES_MODEL_PROVIDER", required=True)
    model_name = environment_value("HERMES_MODEL_NAME", required=True)
    base_url = environment_value("HERMES_MODEL_BASE_URL")
    api_mode = environment_value("HERMES_MODEL_API_MODE")
    reasoning_effort = environment_value("HERMES_REASONING_EFFORT")
    if api_mode and api_mode not in API_MODES:
        raise ValueError("HERMES_MODEL_API_MODE is unsupported")
    if reasoning_effort and reasoning_effort not in REASONING_EFFORTS:
        raise ValueError("HERMES_REASONING_EFFORT is unsupported")

    model: dict[str, Any] = {
        "provider": provider,
        "name": model_name,
        "default": model_name,
    }
    if base_url:
        model["base_url"] = base_url
    if api_mode:
        model["api_mode"] = api_mode

    delegation: dict[str, Any] = {
        "max_concurrent_children": environment_integer(
            "HERMES_MAX_CONCURRENT_CHILDREN",
            3,
            minimum=1,
        ),
        "max_spawn_depth": environment_integer(
            "HERMES_MAX_SPAWN_DEPTH",
            1,
            minimum=1,
            maximum=3,
        ),
        "orchestrator_enabled": environment_boolean(
            "HERMES_ORCHESTRATOR_ENABLED",
            True,
        ),
    }
    delegation_provider = environment_value("HERMES_DELEGATION_PROVIDER")
    delegation_model = environment_value("HERMES_DELEGATION_MODEL")
    if delegation_provider:
        delegation["provider"] = delegation_provider
    if delegation_model:
        delegation["model"] = delegation_model

    agent: dict[str, Any] = {"image_input_mode": "text"}
    if reasoning_effort:
        agent["reasoning_effort"] = reasoning_effort

    return {
        "agent": {
            **agent,
        },
        "model": model,
        "delegation": delegation,
        "mcp_servers": {
            "barbarossa": {
                "command": "/opt/barbarossa-router/barbarossa-router.pex",
                "args": ["serve"],
                "supports_parallel_tool_calls": True,
                "connect_timeout": 15,
                "timeout": 30,
                "env": {
                    "BARBAROSSA_SSH_KEY": "/run/secrets/worker_key",
                    "BARBAROSSA_KNOWN_HOSTS": "/run/secrets/known_hosts",
                    "BARBAROSSA_STATE_DB": "/opt/data/router/jobs.sqlite3",
                    "BARBAROSSA_INPUT_ROOT": (
                        "/opt/data/barbarossa-transfer"
                    ),
                    "BARBAROSSA_RESULT_ROOT": (
                        "/opt/data/barbarossa-results"
                    ),
                    "BARBAROSSA_FORGE_HOST": "forge",
                    "BARBAROSSA_RECON_HOST": "recon",
                    "OTEL_SDK_DISABLED": "true",
                },
            }
        },
    }


def configure(path: Path = CONFIG_PATH) -> None:
    if path.exists():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if loaded is None:
            config: dict[str, Any] = {}
        elif isinstance(loaded, dict):
            config = loaded
        else:
            raise ValueError("Hermes config must contain a YAML mapping")
    else:
        config = {}

    desired = desired_config()
    config["model"] = desired.pop("model")
    delegation = config.get("delegation")
    if isinstance(delegation, dict):
        for key in ("provider", "model", "base_url", "api_key", "api_mode"):
            delegation.pop(key, None)
    merge(config, desired)
    agent = config["agent"]
    disabled_toolsets = agent.get("disabled_toolsets")
    if not isinstance(disabled_toolsets, list):
        disabled_toolsets = []
        agent["disabled_toolsets"] = disabled_toolsets
    if "vision" not in disabled_toolsets:
        disabled_toolsets.append("vision")

    serialized = yaml.safe_dump(
        config,
        allow_unicode=False,
        default_flow_style=False,
        sort_keys=False,
    )
    validated = yaml.safe_load(serialized)
    if not isinstance(validated, dict):
        raise ValueError("generated Hermes config is invalid")

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=".config.yaml.",
        dir=path.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(serialized)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def install_context(
    source_root: Path = CONTEXT_ROOT,
    data_root: Path = DATA_ROOT,
) -> None:
    agents_source = source_root / "AGENTS.md"
    if agents_source.is_file():
        destination = data_root / "AGENTS.md"
        descriptor, temporary = tempfile.mkstemp(
            prefix=".AGENTS.md.",
            dir=data_root,
        )
        os.close(descriptor)
        try:
            shutil.copyfile(agents_source, temporary)
            os.chmod(temporary, 0o600)
            os.replace(temporary, destination)
        except Exception:
            Path(temporary).unlink(missing_ok=True)
            raise

    skills_source = source_root / "skills"
    skills_destination = data_root / "skills"
    skills_destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    for source in sorted(skills_source.glob("barbarossa-*")):
        if not source.is_dir() or source.is_symlink():
            continue
        destination = skills_destination / source.name
        if destination.is_symlink() or destination.is_file():
            destination.unlink()
        elif destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)


if __name__ == "__main__":
    install_context()
    configure()
