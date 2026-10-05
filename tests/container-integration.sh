#!/bin/sh
set -eu

root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
target="${1:-all}"
forge_image="${BARBAROSSA_FORGE_TEST_IMAGE:-barbarossa-forge:test}"
recon_image="${BARBAROSSA_RECON_TEST_IMAGE:-barbarossa-recon:test}"

build_forge() {
  if [ -z "${BARBAROSSA_FORGE_TEST_IMAGE:-}" ]; then
    docker build --file "$root/containers/forge/Dockerfile" --tag "$forge_image" "$root"
  fi

  docker run --rm --entrypoint codex "$forge_image" --version |
    grep -F 'codex-cli 0.154.0'
  docker run --rm --entrypoint id "$forge_image" -u forge |
    grep -Fx '10001'
  docker run --rm --entrypoint test "$forge_image" \
    ! -S /var/run/docker.sock
  docker run --rm --entrypoint python3 "$forge_image" \
    /usr/local/bin/barbarossa-worker self-test |
    grep -F '"status":"ok"'
  docker run --rm --user forge --entrypoint python3 \
    "$forge_image" -c \
    'import tomllib; tomllib.load(open("/home/forge/.codex/config.toml","rb"))'
  docker run --rm --read-only --tmpfs /tmp:rw,nosuid,nodev,size=64m \
    --volume /home/forge \
    --user forge -e HOME=/home/forge --entrypoint sh "$forge_image" -c '
      set -eu
      node --version | grep -F v24.21.0
      npm --version | grep -Fx 12.0.2
      vercel --version 2>&1 | grep -F 59.16.0
      supabase --version | grep -Fx 2.117.0
      uv --version | grep -F 0.12.13
      specify --help >/dev/null
    '
  docker run --rm --user forge -e HOME=/home/forge \
    --entrypoint codex "$forge_image" exec \
    --model gpt-5.6-luna \
    --config 'model_reasoning_effort="high"' \
    --config 'agents.max_concurrent_threads_per_session=1' \
    --strict-config --help >/dev/null
}

build_recon() {
  if [ -z "${BARBAROSSA_RECON_TEST_IMAGE:-}" ]; then
    docker build --file "$root/containers/recon/Dockerfile" --tag "$recon_image" "$root"
  fi

  docker run --rm --entrypoint id "$recon_image" -u recon |
    grep -Fx '10002'
  docker run --rm --entrypoint sh "$recon_image" -lc \
    'command -v nmap && command -v subfinder && command -v torsocks'
  docker run --rm --user recon -e HOME=/home/recon \
    --entrypoint subfinder "$recon_image" -version 2>&1 |
    grep -F 'Current Version: v2.16.0'
  docker run --rm --user recon --entrypoint cat "$recon_image" \
    /home/recon/.config/subfinder/provider-config.yaml |
    grep -Fx '{}'
  docker run --rm --user recon -e HOME=/home/recon \
    --entrypoint katana "$recon_image" -version 2>&1 |
    grep -F 'Current version: v1.7.0'
  docker run --rm --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,nodev,size=16m \
    --user recon -e HOME=/home/recon \
    --entrypoint tlsx "$recon_image" -version 2>&1 |
    grep -F 'Current version: v1.4.0'
  docker run --rm --entrypoint getcap "$recon_image" \
    /usr/bin/masscan /usr/bin/nmap /usr/local/bin/naabu |
    grep -F 'cap_net_admin,cap_net_raw=eip'
  docker run --rm --read-only --tmpfs /tmp:rw,noexec,nosuid,nodev,size=32m \
    --user recon -e HOME=/home/recon --entrypoint sh "$recon_image" -c '
      set -eu
      dnsx -version 2>&1 | grep -F 1.3.1
      httpx -version 2>&1 | grep -F 1.12.0
      nuclei -version 2>&1 | grep -F 3.11.1
      ffuf -V 2>&1 | grep -F 2.3.0
    '
  # Regression guard for the read-only rootfs: katana and ffuf write
  # $XDG_CONFIG_HOME, which the worker redirects to the job scratch.
  docker run --rm --read-only --tmpfs /tmp:rw,noexec,nosuid,nodev,size=64m \
    --user recon -e HOME=/home/recon --entrypoint sh "$recon_image" -c '
      set -eu
      mkdir -p /tmp/cfg /tmp/cache /tmp/site /tmp/wl
      export XDG_CONFIG_HOME=/tmp/cfg XDG_CACHE_HOME=/tmp/cache
      printf "fixture\n" > /tmp/site/admin
      printf "admin\nmissing\n" > /tmp/wl/words.txt
      cd /tmp/site
      python3 -m http.server 18080 >/dev/null 2>&1 &
      server=$!
      trap "kill $server 2>/dev/null || true" EXIT
      sleep 1.5
      ffuf -u http://127.0.0.1:18080/FUZZ -w /tmp/wl/words.txt -mc 200 -s \
        2>/tmp/ffuf.err | grep -F admin
      katana -u http://127.0.0.1:18080 -d 1 -silent >/tmp/katana.out \
        2>/tmp/katana.err
      ! grep -F "read-only file system" /tmp/katana.err
    '
  docker run --rm --entrypoint python3 "$recon_image" \
    /usr/local/bin/barbarossa-worker self-test |
    grep -F '"status":"ok"'
  docker run --rm --entrypoint grep "$recon_image" \
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
