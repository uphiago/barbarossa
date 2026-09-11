"""Exercise deployment failure boundaries without touching a Docker daemon."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[1]
SERVICES = ("forge", "recon", "hermes")
RUNTIME_FILES = (
    "worker_key", "worker_key.pub", "authorized_keys", "known_hosts",
    "codex_auth.json", "github_token", "gmail_user", "gmail_app_password",
    "barbarossa-router.pex", "compose.env",
)

FAKE_DOCKER = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
runtime = Path(os.environ["FAKE_RUNTIME"])
log = Path(os.environ["FAKE_LOG"])
config = {}
compose_args = []
if args and args[0] == "compose":
    i = 1
    while i < len(args) and args[i] in ("--env-file", "-f"):
        option, name = args[i:i+2]
        if option == "--env-file":
            for line in Path(name).read_text().splitlines():
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    config[key] = value.strip("'\"")
        elif Path(name).name == "images.yml":
            config["rollback"] = name
        i += 2
    compose_args = args[i:]
    for key in ("BARBAROSSA_IMAGE_TAG", "BARBAROSSA_RUNTIME_DIR"):
        if key in os.environ:
            config[key] = os.environ[key]
record = {"args": args, "command": compose_args,
          "tag": config.get("BARBAROSSA_IMAGE_TAG"),
          "runtime": config.get("BARBAROSSA_RUNTIME_DIR"),
          "rollback": config.get("rollback"),
          "files": {p.name: p.read_text() for p in runtime.iterdir() if p.is_file()}}
with log.open("a") as f:
    f.write(json.dumps(record) + "\n")
failure = os.environ.get("FAKE_FAIL", "")
if args[0] == "pull":
    if failure == "bundle-pull":
        sys.exit(21)
elif args[0] == "create":
    print("staged-bundle")
elif args[0] == "cp":
    if failure == "bundle-copy":
        sys.exit(22)
    Path(args[-1]).write_text("candidate pex\n" if failure != "bundle-empty" else "")
elif args[0] == "inspect":
    if "config_files" in args[2]:
        print(os.environ["FAKE_PREVIOUS_COMPOSE"])
    else:
        print("sha256:" + args[-1].removeprefix("container-") + "-old")
elif compose_args:
    cmd = compose_args[0]
    if cmd == "config":
        print(json.dumps({"services": {"hermes": {"image": "previous"}}}))
    elif cmd == "ps":
        print("container-" + compose_args[-1])
    elif cmd == "pull":
        if failure in ("worker-pull", "hermes-pull") and (
            failure == "worker-pull" or "hermes" in compose_args
        ):
            sys.exit(23)
    elif cmd == "up":
        rollback = bool(config.get("rollback"))
        if failure in ("worker-start", "hermes-start", "rollback-start") and not rollback:
            service = "hermes" if failure == "hermes-start" else "forge"
            if service in compose_args:
                sys.exit(24)
        if failure == "rollback-start" and rollback:
            sys.exit(25)
    elif cmd == "exec":
        service = compose_args[compose_args.index("-T") + 1]
        if failure == "host-key" and service == "recon":
            sys.exit(26)
        print("ssh-ed25519 " + service + "-public")
sys.exit(0)
'''


@pytest.fixture
def deployment(tmp_path):
    root = tmp_path / "checkout"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    for filename in ("deploy-runtime-files.sh", "compose.sh"):
        shutil.copy2(ROOT / "scripts" / filename, scripts / filename)
    smoke = scripts / "smoke-remote.sh"
    smoke.write_text('#!/bin/sh\n[ "$FAKE_FAIL" != smoke ]\n')
    smoke.chmod(0o755)
    shutil.copy2(ROOT / "docker-compose.yml", root / "docker-compose.yml")
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (root / ".env").write_text(
        f"BARBAROSSA_RUNTIME_DIR={runtime}\nBARBAROSSA_IMAGE_TAG=stale-dotenv\n"
    )
    (runtime / "codex_auth.json").write_text('{"fake": "credential"}\n')
    (runtime / "github_token").write_text("fake-github\n")
    (runtime / "gmail_user").write_text("fake-user\n")
    (runtime / "gmail_app_password").write_text("fake-password\n")
    subprocess.run([
        "ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(runtime / "worker_key")
    ], check=True)
    (runtime / "authorized_keys").write_text(
        'restrict,command="/usr/local/bin/worker-ssh-dispatch" '
        + (runtime / "worker_key.pub").read_text()
    )
    (runtime / "known_hosts").write_text(
        "forge ssh-ed25519 forge-public\nrecon ssh-ed25519 recon-public\n"
    )
    (runtime / "barbarossa-router.pex").write_text("previous pex\n")
    (runtime / "compose.env").write_text(
        f"BARBAROSSA_IMAGE_TAG=previous\nBARBAROSSA_RUNTIME_DIR={runtime}\n"
    )
    (runtime / "persistent-state").mkdir()
    (runtime / "persistent-state" / "marker").write_text("retained job\n")
    fake = tmp_path / "docker"
    fake.write_text(textwrap.dedent(FAKE_DOCKER))
    fake.chmod(0o755)
    env = os.environ | {
        "DOCKER": str(fake), "FAKE_RUNTIME": str(runtime),
        "FAKE_LOG": str(tmp_path / "docker.jsonl"),
        "BARBAROSSA_RUNTIME_DIR": str(runtime), "BARBAROSSA_IMAGE_TAG": "candidate",
        "FAKE_PREVIOUS_COMPOSE": str(root / "docker-compose.yml"),
    }
    return root, runtime, env


def snapshot(runtime):
    return {name: (runtime / name).read_bytes() for name in RUNTIME_FILES if (runtime / name).exists()}


def execute(deployment, failure="", script="deploy-runtime-files.sh", arguments=()):
    root, runtime, env = deployment
    result = subprocess.run(
        [str(root / "scripts" / script), *arguments],
        env=env | {"FAKE_FAIL": failure}, text=True, capture_output=True,
    )
    log = Path(env["FAKE_LOG"])
    records = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return result, records


def startup(records):
    return [record for record in records if record["command"][:1] == ["up"]]


@pytest.mark.parametrize("failure", ["bundle-pull", "bundle-copy", "hermes-pull", "worker-pull"])
def test_download_failure_keeps_live_files_and_services_untouched(deployment, failure):
    _, runtime, _ = deployment
    original = snapshot(runtime)
    result, records = execute(deployment, failure)
    assert result.returncode != 0
    assert snapshot(runtime) == original
    assert not startup(records)
    assert not any(r["command"][:1] in (["down"], ["stop"]) for r in records)
    assert not any(r["args"][:2] == ["volume", "rm"] for r in records)


def test_upgrade_preserves_credentials_state_and_rollback_release(deployment):
    _, runtime, _ = deployment
    original = snapshot(runtime)
    result, records = execute(deployment)
    assert result.returncode == 0, result.stderr
    for name in RUNTIME_FILES:
        if name not in ("compose.env", "barbarossa-router.pex"):
            assert (runtime / name).read_bytes() == original[name]
    assert (runtime / "persistent-state" / "marker").read_text() == "retained job\n"
    assert (runtime / "barbarossa-router.pex").read_text() == "candidate pex\n"
    releases = list((runtime / "rollback").iterdir())
    assert len(releases) == 1
    release = releases[0]
    assert (release / "compose.env").read_bytes() == original["compose.env"]
    assert (release / "barbarossa-router.pex").read_bytes() == original["barbarossa-router.pex"]
    assert (release / "images.yml").is_file()
    tags = [r for r in records if r["args"][:2] == ["image", "tag"]]
    assert len(tags) == 3
    for service in SERVICES:
        assert any(r["args"][2] == f"sha256:{service}-old" for r in tags)
        assert f"barbarossa-rollback-{service}:" in (release / "images.yml").read_text()
    assert not any(r["command"][:1] == ["down"] for r in records)
    assert not any(r["args"][:2] in (["volume", "rm"], ["image", "rm"], ["image", "prune"]) for r in records)
    first_up = records.index(startup(records)[0])
    downloads = [i for i, r in enumerate(records) if r["args"][0] in ("pull", "cp") or r["command"][:1] == ["pull"]]
    assert max(downloads) < first_up
    assert any("hermes" in r["command"] for r in records if r["command"][:1] == ["pull"])
    assert all(r["tag"] == "candidate" for r in startup(records))
    assert "--force-recreate" in startup(records)[-1]["command"]
    assert (release.stat().st_mode & 0o777) == 0o700


@pytest.mark.parametrize("failure", ["worker-start", "hermes-start", "host-key", "smoke"])
def test_startup_failure_restores_previous_files_and_recreates_previous_images(deployment, failure):
    _, runtime, _ = deployment
    original = snapshot(runtime)
    result, records = execute(deployment, failure)
    assert result.returncode != 0
    assert snapshot(runtime) == original
    rollback = [r for r in startup(records) if r["rollback"]]
    assert rollback
    assert all(r["tag"] == "previous" for r in rollback)
    assert all("--force-recreate" in r["command"] for r in rollback)
    assert set(SERVICES).issubset(set(sum((r["command"] for r in rollback), [])))
    assert all(r["files"]["barbarossa-router.pex"] == "previous pex\n" for r in rollback)
    assert "rollback" in result.stderr.lower()


@pytest.mark.parametrize("missing", ["worker_key", "worker_key.pub", "authorized_keys", "known_hosts", "compose.env", "barbarossa-router.pex"])
def test_partial_existing_install_is_rejected_without_mutations(deployment, missing):
    _, runtime, _ = deployment
    (runtime / missing).unlink()
    original = snapshot(runtime)
    result, records = execute(deployment)
    assert result.returncode != 0
    assert snapshot(runtime) == original
    assert not startup(records)


def test_atomic_pex_replacement_keeps_old_open_inode_until_recreation(deployment):
    _, runtime, _ = deployment
    with (runtime / "barbarossa-router.pex").open() as old_mount:
        result, records = execute(deployment)
        assert result.returncode == 0, result.stderr
        assert old_mount.read() == "previous pex\n"
    assert (runtime / "barbarossa-router.pex").read_text() == "candidate pex\n"
    assert any("hermes" in r["command"] and "--force-recreate" in r["command"] for r in startup(records))


def test_operator_compose_uses_runtime_release_over_dotenv_and_shell(deployment):
    _, runtime, _ = deployment
    result, records = execute(deployment, script="compose.sh", arguments=("ps",))
    assert result.returncode == 0, result.stderr
    assert records[-1]["tag"] == "previous"
    assert records[-1]["runtime"] == str(runtime)


def test_fresh_bootstrap_creates_keys_only_after_staging_images(deployment):
    _, runtime, _ = deployment
    for name in ("worker_key", "worker_key.pub", "authorized_keys", "known_hosts", "compose.env", "barbarossa-router.pex"):
        (runtime / name).unlink()
    result, records = execute(deployment)
    assert result.returncode == 0, result.stderr
    assert (runtime / "worker_key").is_file()
    assert (runtime / "known_hosts").read_text() == "forge ssh-ed25519 forge-public\nrecon ssh-ed25519 recon-public\n"
    for record in records:
        if record["args"][0] in ("pull", "cp") or record["command"][:1] == ["pull"]:
            assert "worker_key" not in record["files"]
