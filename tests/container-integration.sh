#!/bin/sh
set -eu

root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
target="${1:-all}"

build_forge() {
  docker build \
    --file "$root/containers/forge/Dockerfile" \
    --tag barbarossa-forge:test \
    "$root"

  docker run --rm --entrypoint codex barbarossa-forge:test --version |
    grep -F 'codex-cli 0.145.0'
  docker run --rm --entrypoint id barbarossa-forge:test -u forge |
    grep -Fx '10001'
  docker run --rm --entrypoint test barbarossa-forge:test \
    ! -S /var/run/docker.sock
  docker run --rm --entrypoint python3 barbarossa-forge:test \
    /usr/local/bin/barbarossa-worker self-test |
    grep -F '"status":"ok"'
  docker run --rm --user forge --entrypoint python3 \
    barbarossa-forge:test -c \
    'import tomllib; tomllib.load(open("/home/forge/.codex/config.toml","rb"))'
}

case "$target" in
  forge)
    build_forge
    ;;
  recon)
    printf 'recon image is not implemented yet\n' >&2
    exit 1
    ;;
  all)
    build_forge
    ;;
  *)
    printf 'usage: %s [forge|recon|all]\n' "$0" >&2
    exit 2
    ;;
esac
