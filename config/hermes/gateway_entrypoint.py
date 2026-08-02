#!/usr/bin/env python3
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path
from typing import Iterable

CACHE_ROOT = Path("/opt/data/cache/images")
TRANSFER_ROOT = Path("/opt/data/barbarossa-transfer")
MAX_IMAGE_BYTES = 50 * 1024 * 1024
IMAGE_SUFFIXES = {
    ".bmp",
    ".gif",
    ".heic",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}


def _validated_source(path: str, cache_root: Path) -> Path:
    source = Path(path).resolve(strict=True)
    root = cache_root.resolve(strict=True)
    try:
        source.relative_to(root)
    except ValueError as error:
        raise ValueError(
            f"image path is outside the Hermes image cache: {source}"
        ) from error

    metadata = source.stat()
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"image path is not a regular file: {source}")
    if source.suffix.lower() not in IMAGE_SUFFIXES:
        raise ValueError(f"unsupported image extension: {source.suffix}")
    if metadata.st_size > MAX_IMAGE_BYTES:
        raise ValueError(f"image exceeds {MAX_IMAGE_BYTES} bytes: {source}")
    return source


def stage_inbound_images(
    image_paths: Iterable[str],
    *,
    cache_root: Path = CACHE_ROOT,
    transfer_root: Path = TRANSFER_ROOT,
) -> list[Path]:
    transfer_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(transfer_root, 0o700)
    staged: list[Path] = []

    for path in image_paths:
        source = _validated_source(path, cache_root)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{source.stem}.",
            suffix=source.suffix.lower(),
            dir=transfer_root,
        )
        os.close(descriptor)
        try:
            shutil.copyfile(source, temporary)
            os.chmod(temporary, 0o600)
            destination = transfer_root / source.name
            os.replace(temporary, destination)
        except Exception:
            Path(temporary).unlink(missing_ok=True)
            raise
        staged.append(destination)

    return staged


async def enrich_message_with_codex(
    _runner: object,
    user_text: str,
    image_paths: list[str],
    *,
    cache_root: Path = CACHE_ROOT,
    transfer_root: Path = TRANSFER_ROOT,
) -> str:
    staged = stage_inbound_images(
        image_paths,
        cache_root=cache_root,
        transfer_root=transfer_root,
    )
    paths = "\n".join(f"- {path}" for path in staged)
    return (
        f"{user_text}\n\n"
        "[System: attached images were staged for isolated Codex vision. "
        "Call media_image_inspect once for each path below with the prompt "
        "argument set to the full user request above verbatim, poll that job, "
        "and answer from its result. Do not call vision_analyze and do not "
        "use the terminal command `file` for these images.]\n"
        f"{paths}"
    )


def main() -> int:
    from gateway.run import GatewayRunner
    from hermes_cli.main import main as hermes_main

    GatewayRunner._enrich_message_with_vision = enrich_message_with_codex
    return hermes_main()


if __name__ == "__main__":
    sys.exit(main())
