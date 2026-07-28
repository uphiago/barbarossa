import asyncio
import importlib.util
import os
from pathlib import Path
from types import ModuleType

import pytest


def load_gateway() -> ModuleType:
    path = (
        Path(__file__).parents[1]
        / "config"
        / "hermes"
        / "gateway_entrypoint.py"
    )
    spec = importlib.util.spec_from_file_location("barbarossa_gateway", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stage_inbound_images_is_private_and_builds_codex_instruction(
    tmp_path: Path,
) -> None:
    gateway = load_gateway()
    cache = tmp_path / "cache"
    transfer = tmp_path / "transfer"
    cache.mkdir()
    source = cache / "attachment.jpg"
    source.write_bytes(b"\xff\xd8\xfftest-image")

    message = asyncio.run(
        gateway.enrich_message_with_codex(
            object(),
            "What is this?",
            [str(source)],
            cache_root=cache,
            transfer_root=transfer,
        )
    )

    staged = transfer / "attachment.jpg"
    assert staged.read_bytes() == source.read_bytes()
    assert os.stat(staged).st_mode & 0o777 == 0o600
    assert str(staged) in message
    assert "media_image_inspect" in message
    assert "vision_analyze" in message
    assert "command `file`" in message


def test_stage_inbound_images_rejects_paths_outside_cache(
    tmp_path: Path,
) -> None:
    gateway = load_gateway()
    cache = tmp_path / "cache"
    transfer = tmp_path / "transfer"
    cache.mkdir()
    source = tmp_path / "outside.jpg"
    source.write_bytes(b"\xff\xd8\xffoutside")

    with pytest.raises(ValueError, match="outside the Hermes image cache"):
        asyncio.run(
            gateway.enrich_message_with_codex(
                object(),
                "Inspect it",
                [str(source)],
                cache_root=cache,
                transfer_root=transfer,
            )
        )
