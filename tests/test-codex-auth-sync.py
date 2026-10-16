import importlib.util
import json
import os
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[1]
SYNC_PATH = ROOT / "containers" / "forge" / "codex-auth-sync.py"

# Fixed clocks keep the mtime tiebreak deterministic on any filesystem.
OLD, NEW = 1_700_000_000.0, 1_700_000_600.0


@pytest.fixture
def sync(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.delenv("CODEX_AUTH_FORCE_INSTALL", raising=False)
    spec = importlib.util.spec_from_file_location("codex_auth_sync", SYNC_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def credential(path: Path, stamp: object, mtime: float | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"tokens": {"access_token": "placeholder"}, "last_refresh": stamp}),
        encoding="utf-8",
    )
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def test_bootstrap_installs_when_target_is_absent(sync: ModuleType, tmp_path: Path) -> None:
    source = credential(tmp_path / "codex_auth.json", "2026-10-13")
    install, reason = sync.decide(source, tmp_path / "volume" / "auth.json", force=False)
    assert install is True
    assert "bootstrap" in reason


def test_strictly_newer_source_stamp_installs(sync: ModuleType, tmp_path: Path) -> None:
    source = credential(tmp_path / "codex_auth.json", "2026-10-13")
    target = credential(tmp_path / "auth.json", "2026-10-02")
    install, _ = sync.decide(source, target, force=False)
    assert install is True


def test_newer_target_stamp_is_kept(sync: ModuleType, tmp_path: Path) -> None:
    """The incident this policy exists for: a used-up token never overwrites a rotated copy."""
    source = credential(tmp_path / "codex_auth.json", "2026-10-02", mtime=NEW)
    target = credential(tmp_path / "auth.json", "2026-10-13", mtime=OLD)
    install, reason = sync.decide(source, target, force=False)
    assert install is False
    assert "target last_refresh is newer" in reason


def test_equal_timestamps_fall_back_to_source_mtime(sync: ModuleType, tmp_path: Path) -> None:
    source = credential(tmp_path / "codex_auth.json", "2026-10-16T15:08:13Z", mtime=NEW)
    target = credential(tmp_path / "auth.json", "2026-10-16T15:08:13Z", mtime=OLD)
    install, reason = sync.decide(source, target, force=False)
    assert install is True
    assert "mtime" in reason


def test_equal_timestamps_keep_a_newer_target_file(sync: ModuleType, tmp_path: Path) -> None:
    source = credential(tmp_path / "codex_auth.json", "2026-10-16T15:08:13Z", mtime=OLD)
    target = credential(tmp_path / "auth.json", "2026-10-16T15:08:13Z", mtime=NEW)
    install, reason = sync.decide(source, target, force=False)
    assert install is False
    assert "not older on disk" in reason


def test_same_day_date_only_rotation_installs(sync: ModuleType, tmp_path: Path) -> None:
    """Two rotations on one day share a day-granularity stamp; the rewritten file wins."""
    source = credential(tmp_path / "codex_auth.json", "2026-10-16", mtime=NEW)
    target = credential(tmp_path / "auth.json", "2026-10-16", mtime=OLD)
    install, _ = sync.decide(source, target, force=False)
    assert install is True


def test_same_day_date_only_rotation_without_newer_mtime_keeps_target(
    sync: ModuleType, tmp_path: Path
) -> None:
    source = credential(tmp_path / "codex_auth.json", "2026-10-16", mtime=OLD)
    target = credential(tmp_path / "auth.json", "2026-10-16", mtime=NEW)
    install, _ = sync.decide(source, target, force=False)
    assert install is False


def test_fractional_seconds_beat_lexicographic_order(sync: ModuleType, tmp_path: Path) -> None:
    """Text comparison calls the sub-second stamp older; the parsed comparison must not."""
    source = credential(tmp_path / "codex_auth.json", "2026-10-16T15:08:13.500000Z")
    target = credential(tmp_path / "auth.json", "2026-10-16T15:08:13Z")
    install, reason = sync.decide(source, target, force=False)
    assert install is True
    assert "source last_refresh is newer" in reason


def test_offsets_are_normalised_to_utc(sync: ModuleType, tmp_path: Path) -> None:
    source = credential(tmp_path / "codex_auth.json", "2026-10-16T12:00:00-03:00")
    target = credential(tmp_path / "auth.json", "2026-10-16T14:00:00+00:00")
    install, _ = sync.decide(source, target, force=False)
    assert install is True


def test_epoch_stamp_compares_against_iso_stamp(sync: ModuleType, tmp_path: Path) -> None:
    source = credential(tmp_path / "codex_auth.json", 2_000_000_000)
    target = credential(tmp_path / "auth.json", "2001-09-09T01:46:40Z")
    install, _ = sync.decide(source, target, force=False)
    assert install is True


@pytest.mark.parametrize("stamp", [None, "", "not-a-timestamp", {"unexpected": "shape"}, True])
def test_unusable_stamp_falls_back_to_mtime(
    sync: ModuleType, tmp_path: Path, stamp: object
) -> None:
    source = credential(tmp_path / "codex_auth.json", stamp, mtime=NEW)
    target = credential(tmp_path / "auth.json", stamp, mtime=OLD)
    install, reason = sync.decide(source, target, force=False)
    assert install is True
    assert "mtime" in reason


def test_absent_stamp_with_older_source_file_keeps_target(sync: ModuleType, tmp_path: Path) -> None:
    source = credential(tmp_path / "codex_auth.json", None, mtime=OLD)
    target = credential(tmp_path / "auth.json", None, mtime=NEW)
    install, _ = sync.decide(source, target, force=False)
    assert install is False


def test_force_overrides_a_newer_target(sync: ModuleType, tmp_path: Path) -> None:
    source = credential(tmp_path / "codex_auth.json", "2026-10-02", mtime=OLD)
    target = credential(tmp_path / "auth.json", "2026-10-13", mtime=NEW)
    install, reason = sync.decide(source, target, force=True)
    assert install is True
    assert "forced" in reason


def test_main_force_flag_and_env_install(
    sync: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = credential(tmp_path / "codex_auth.json", "2026-10-02", mtime=OLD)
    target = credential(tmp_path / "auth.json", "2026-10-13", mtime=NEW)
    assert sync.main([str(source), str(target), "--force"]) == 0
    assert "install" in capsys.readouterr().out
    monkeypatch.setenv("CODEX_AUTH_FORCE_INSTALL", "1")
    assert sync.main([str(source), str(target)]) == 0


def test_main_returns_one_when_the_target_is_newer(sync: ModuleType, tmp_path: Path) -> None:
    source = credential(tmp_path / "codex_auth.json", "2026-10-02", mtime=OLD)
    target = credential(tmp_path / "auth.json", "2026-10-13", mtime=NEW)
    assert sync.main([str(source), str(target)]) == 1


def test_main_requires_two_paths(sync: ModuleType, tmp_path: Path) -> None:
    source = credential(tmp_path / "codex_auth.json", "2026-10-13")
    assert sync.main([str(source)]) == 2


def test_main_rejects_a_missing_or_empty_source(sync: ModuleType, tmp_path: Path) -> None:
    empty = tmp_path / "empty.json"
    empty.write_text("", encoding="utf-8")
    assert sync.main([str(tmp_path / "absent.json"), str(tmp_path / "auth.json")]) == 2
    assert sync.main([str(empty), str(tmp_path / "auth.json")]) == 2
