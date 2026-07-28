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


def merge(target: dict[str, Any], updates: dict[str, Any]) -> None:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            merge(target[key], value)
        else:
            target[key] = value


def desired_config() -> dict[str, Any]:
    return {
        "agent": {
            "image_input_mode": "text",
        },
        "model": {
            "provider": "deepseek",
            "name": "deepseek-v4-flash",
            "default": "deepseek-v4-flash",
            "base_url": "https://api.deepseek.com/v1",
        },
        "delegation": {
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "max_concurrent_children": 3,
            "max_spawn_depth": 1,
            "orchestrator_enabled": True,
        },
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

    model = config.get("model")
    if isinstance(model, dict):
        model.pop("api_key", None)
        model.pop("api_mode", None)

    merge(config, desired_config())
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
