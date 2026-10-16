#!/usr/bin/env python3
"""Decide whether a deployed Codex credential may replace the copy in place.

ChatGPT credentials (`auth_mode: chatgpt`) use rotating refresh tokens: every
refresh consumes the previous token, so the copy inside the container volume
drifts ahead of the credential deployed from the host. This helper owns that
decision, which keeps it testable outside the container entrypoint.

Install policy, evaluated in order:

1. the target is absent              -> install (volume bootstrap)
2. force requested                   -> install (`--force`, or a truthy
                                        CODEX_AUTH_FORCE_INSTALL)
3. both `last_refresh` stamps parse
   and differ                        -> install only when the source is
                                        strictly newer
4. stamps equal, absent or unusable  -> install only when the source file is
                                        strictly newer on disk (mtime), which is
                                        what a deliberate rotation rewrites

Every ambiguous case resolves to "keep the target": a used-up refresh token must
never clobber a rotated copy. Stamps are compared as parsed timestamps, never as
text — `2026-10-16T15:08:13.500000Z` is newer than `2026-10-16T15:08:13Z`, while
a lexicographic comparison of those two strings claims the opposite. Stamps with
day granularity (for example `2026-10-13`) are equal for two rotations on the
same day, which is why case 4 falls through to the file mtime; pass `--force` /
CODEX_AUTH_FORCE_INSTALL=1 when the rotation must win regardless.

Exit codes: 0 install, 1 keep the target, 2 usage error.
"""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import sys

TRUTHY = {"1", "true", "yes", "on"}


def parse_stamp(raw: object) -> datetime.datetime | None:
    """Return an aware UTC datetime for a Codex ``last_refresh`` value."""
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, (int, float)):
        try:
            return datetime.datetime.fromtimestamp(float(raw), tz=datetime.timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    if text[-1] in "Zz":
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def read_stamp(path: pathlib.Path) -> object:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value.get("last_refresh") if isinstance(value, dict) else None


def _mtime(path: pathlib.Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def decide(source: pathlib.Path, target: pathlib.Path, force: bool) -> tuple[bool, str]:
    if not target.exists():
        return True, "target missing (bootstrap)"
    if force:
        return True, "forced by --force/CODEX_AUTH_FORCE_INSTALL"
    source_stamp = parse_stamp(read_stamp(source))
    target_stamp = parse_stamp(read_stamp(target))
    if source_stamp is not None and target_stamp is not None and source_stamp != target_stamp:
        if source_stamp > target_stamp:
            return True, f"source last_refresh is newer ({source_stamp.isoformat()})"
        return False, f"target last_refresh is newer ({target_stamp.isoformat()})"
    detail = (
        "last_refresh stamps are equal"
        if source_stamp is not None and source_stamp == target_stamp
        else "last_refresh is absent or unusable"
    )
    source_mtime = _mtime(source)
    target_mtime = _mtime(target)
    if source_mtime is None or target_mtime is None:
        return False, f"{detail}; file mtime unavailable"
    if source_mtime > target_mtime:
        return True, f"{detail}; source file is newer on disk (mtime)"
    return False, f"{detail}; target file is not older on disk (mtime)"


def main(argv: list[str]) -> int:
    positional = [item for item in argv if not item.startswith("-")]
    force = "--force" in argv or os.environ.get("CODEX_AUTH_FORCE_INSTALL", "").strip().lower() in TRUTHY
    if len(positional) != 2:
        print("usage: codex-auth-sync.py <source> <target> [--force]", file=sys.stderr)
        return 2
    source, target = (pathlib.Path(item) for item in positional)
    if not source.is_file() or not source.stat().st_size:
        print(f"codex-auth-sync: source {source} is missing or empty", file=sys.stderr)
        return 2
    install, reason = decide(source, target, force)
    print(f"codex-auth-sync: {'install' if install else 'keep target'}: {reason}")
    return 0 if install else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
