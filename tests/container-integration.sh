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
  docker run --rm --user forge -e CODEX_ACCESS_TOKEN=invalid \
    --entrypoint codex barbarossa-forge:test \
    exec --model gpt-5.6-luna \
    --config 'model_reasoning_effort="high"' \
    --config 'agents.max_concurrent_threads_per_session=1' \
    --strict-config --skip-git-repo-check --json 'reply OK' \
    2>&1 | grep -F 'invalid agent identity JWT format'
}

build_recon() {
  docker build \
    --file "$root/containers/recon/Dockerfile" \
    --tag barbarossa-recon:test \
    "$root"

  docker run --rm --entrypoint id barbarossa-recon:test -u recon |
    grep -Fx '10002'
  docker run --rm --entrypoint sh barbarossa-recon:test -lc \
    'command -v nmap && command -v subfinder && command -v torsocks'
  docker run --rm --user recon -e HOME=/home/recon \
    --entrypoint subfinder barbarossa-recon:test -version 2>&1 |
    grep -F 'Current Version: v2.14.0'
  docker run --rm --user recon --entrypoint cat barbarossa-recon:test \
    /home/recon/.config/subfinder/provider-config.yaml |
    grep -Fx '{}'
  docker run --rm --user recon -e HOME=/home/recon \
    --entrypoint katana barbarossa-recon:test -version 2>&1 |
    grep -F 'Current version: v1.6.1'
  docker run --rm --user recon -e HOME=/home/recon \
    --entrypoint tlsx barbarossa-recon:test -version 2>&1 |
    grep -F 'Current version: v1.2.2'
  docker run --rm --entrypoint getcap barbarossa-recon:test \
    /usr/bin/masscan /usr/bin/nmap /usr/local/bin/naabu |
    grep -F 'cap_net_admin,cap_net_raw=eip'
  docker run --rm --entrypoint python3 barbarossa-recon:test \
    /usr/local/bin/barbarossa-worker self-test |
    grep -F '"status":"ok"'
  docker run --rm --entrypoint grep barbarossa-recon:test \
    -Fx 'SocksPort 127.0.0.1:9050' /etc/tor/torrc
}

case "$target" in
  forge)
    build_forge
    ;;
  recon)
    build_recon
    ;;
  all)
    build_forge
    build_recon
    ;;
  *)
    printf 'usage: %s [forge|recon|all]\n' "$0" >&2
    exit 2
    ;;
esac
