#!/bin/bash
set -euo pipefail

root="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$root"

for command in docker ssh-keygen uv python3; do
  command -v "$command" >/dev/null || {
    printf 'missing required command: %s\n' "$command" >&2
    exit 1
  }
done
docker compose version >/dev/null

test -f .env || {
  printf 'missing .env; start from .env.example\n' >&2
  exit 1
}
set -a
# shellcheck disable=SC1091
. "$root/.env"
set +a

for variable in \
  DEEPSEEK_API_KEY TELEGRAM_BOT_TOKEN \
  DASHBOARD_USER DASHBOARD_PASS DASHBOARD_SECRET; do
  test -n "${!variable:-}" || {
    printf 'missing required variable: %s\n' "$variable" >&2
    exit 1
  }
done

runtime="${BARBAROSSA_RUNTIME_DIR:-$root/.runtime}"
install -d -m 0700 "$runtime"
umask 077

export BARBAROSSA_WORKER_SSH_KEY_FILE="$runtime/worker_key"
export BARBAROSSA_AUTHORIZED_KEYS_FILE="$runtime/authorized_keys"
export BARBAROSSA_KNOWN_HOSTS_FILE="$runtime/known_hosts"
export BARBAROSSA_CODEX_TOKEN_FILE="${BARBAROSSA_CODEX_TOKEN_FILE:-$runtime/codex_access_token}"
export BARBAROSSA_CODEX_AUTH_FILE="${BARBAROSSA_CODEX_AUTH_FILE:-$runtime/codex_auth.json}"
export BARBAROSSA_ROUTER_BUNDLE="$runtime/barbarossa-router.pex"
export BARBAROSSA_IMAGE_TAG="${BARBAROSSA_IMAGE_TAG:-local}"

if [ -n "${CODEX_ACCESS_TOKEN:-}" ]; then
  printf '%s' "$CODEX_ACCESS_TOKEN" > "$BARBAROSSA_CODEX_TOKEN_FILE"
fi
touch "$BARBAROSSA_CODEX_TOKEN_FILE"
if [ ! -s "$BARBAROSSA_CODEX_TOKEN_FILE" ] &&
  [ ! -s "$BARBAROSSA_CODEX_AUTH_FILE" ] &&
  [ -s "$HOME/.codex/auth.json" ]; then
  install -m 0644 "$HOME/.codex/auth.json" \
    "$BARBAROSSA_CODEX_AUTH_FILE"
fi
if [ ! -s "$BARBAROSSA_CODEX_TOKEN_FILE" ] &&
  [ ! -s "$BARBAROSSA_CODEX_AUTH_FILE" ]; then
  printf 'missing Codex access token or auth.json\n' >&2
  exit 1
fi
touch "$BARBAROSSA_CODEX_AUTH_FILE"
chmod 0644 "$BARBAROSSA_CODEX_TOKEN_FILE" \
  "$BARBAROSSA_CODEX_AUTH_FILE"

rm -f "$BARBAROSSA_WORKER_SSH_KEY_FILE" \
  "$BARBAROSSA_WORKER_SSH_KEY_FILE.pub" \
  "$BARBAROSSA_AUTHORIZED_KEYS_FILE" \
  "$BARBAROSSA_KNOWN_HOSTS_FILE"
ssh-keygen -q -t ed25519 -N "" -C "hermes@barbarossa-local" \
  -f "$BARBAROSSA_WORKER_SSH_KEY_FILE"
printf 'restrict,command="/usr/local/bin/worker-ssh-dispatch" %s\n' \
  "$(cat "$BARBAROSSA_WORKER_SSH_KEY_FILE.pub")" \
  > "$BARBAROSSA_AUTHORIZED_KEYS_FILE"
touch "$BARBAROSSA_KNOWN_HOSTS_FILE"
chmod 0644 "$BARBAROSSA_WORKER_SSH_KEY_FILE" \
  "$BARBAROSSA_AUTHORIZED_KEYS_FILE" \
  "$BARBAROSSA_KNOWN_HOSTS_FILE"

(
  cd router
  mkdir -p dist
  uv export --quiet --frozen --no-dev --no-emit-project \
    --format requirements-txt \
    --output-file dist/runtime-requirements.txt
  uv run --frozen --group bundle pex \
    -r dist/runtime-requirements.txt \
    -D src \
    -o "$BARBAROSSA_ROUTER_BUNDLE" \
    --python-shebang=/opt/hermes/.venv/bin/python \
    -e barbarossa_router.cli:main
)
chmod 0555 "$BARBAROSSA_ROUTER_BUNDLE"

docker compose down --remove-orphans
docker compose build forge recon
docker compose up -d --remove-orphans --force-recreate \
  --wait --wait-timeout 300 forge recon

{
  printf 'forge %s\n' \
    "$(docker compose exec -T forge \
      cat /ssh-host-keys/ssh_host_ed25519_key.pub)"
  printf 'recon %s\n' \
    "$(docker compose exec -T recon \
      cat /ssh-host-keys/ssh_host_ed25519_key.pub)"
} > "$BARBAROSSA_KNOWN_HOSTS_FILE"
chmod 0644 "$BARBAROSSA_KNOWN_HOSTS_FILE"

docker compose up -d --remove-orphans --force-recreate \
  --wait --wait-timeout 300 hermes
BARBAROSSA_RUNTIME_DIR="$runtime" scripts/smoke-remote.sh
