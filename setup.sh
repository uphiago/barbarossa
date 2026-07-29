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

hermes_env="${BARBAROSSA_HERMES_ENV_FILE:-$root/hermes.env}"
case "$hermes_env" in
  /*) ;;
  *) hermes_env="$root/${hermes_env#./}" ;;
esac
test -f "$hermes_env" || {
  printf 'missing Hermes configuration: %s\n' "$hermes_env" >&2
  exit 1
}
docker compose --env-file "$root/.env" \
  -f "$root/docker-compose.yml" config --format json |
  python3 -c '
import json
import sys

environment = json.load(sys.stdin)["services"]["hermes"]["environment"]
required = (
    "HERMES_MODEL_PROVIDER",
    "HERMES_MODEL_NAME",
    "TELEGRAM_BOT_TOKEN",
    "HERMES_DASHBOARD_BASIC_AUTH_USERNAME",
    "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD",
    "HERMES_DASHBOARD_BASIC_AUTH_SECRET",
)
missing = [name for name in required if not environment.get(name)]
if missing:
    raise SystemExit("missing required Hermes variables: " + ", ".join(missing))
'

runtime="${BARBAROSSA_RUNTIME_DIR:-$root/.runtime}"
case "$runtime" in
  /*) ;;
  *) runtime="$root/${runtime#./}" ;;
esac
install -d -m 0700 "$runtime"
umask 077

export BARBAROSSA_WORKER_SSH_KEY_FILE="$runtime/worker_key"
export BARBAROSSA_AUTHORIZED_KEYS_FILE="$runtime/authorized_keys"
export BARBAROSSA_KNOWN_HOSTS_FILE="$runtime/known_hosts"
export BARBAROSSA_CODEX_AUTH_FILE="${BARBAROSSA_CODEX_AUTH_FILE:-$runtime/codex_auth.json}"
export BARBAROSSA_GITHUB_TOKEN_FILE="${BARBAROSSA_GITHUB_TOKEN_FILE:-$runtime/github_token}"
export BARBAROSSA_ROUTER_BUNDLE="$runtime/barbarossa-router.pex"
export BARBAROSSA_IMAGE_TAG="${BARBAROSSA_IMAGE_TAG:-local}"
cat > "$runtime/compose.env" <<EOF
BARBAROSSA_IMAGE_TAG=$BARBAROSSA_IMAGE_TAG
BARBAROSSA_RUNTIME_DIR=$runtime
EOF
chmod 0600 "$runtime/compose.env"

if [ ! -s "$BARBAROSSA_CODEX_AUTH_FILE" ] &&
  [ -s "$HOME/.codex/auth.json" ]; then
  install -m 0644 "$HOME/.codex/auth.json" \
    "$BARBAROSSA_CODEX_AUTH_FILE"
fi
if [ ! -s "$BARBAROSSA_CODEX_AUTH_FILE" ]; then
  printf 'missing Codex auth.json\n' >&2
  exit 1
fi
touch "$BARBAROSSA_CODEX_AUTH_FILE" "$BARBAROSSA_GITHUB_TOKEN_FILE"
chmod 0600 "$BARBAROSSA_CODEX_AUTH_FILE" \
  "$BARBAROSSA_GITHUB_TOKEN_FILE"

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
chmod 0600 "$BARBAROSSA_WORKER_SSH_KEY_FILE"
chmod 0644 "$BARBAROSSA_AUTHORIZED_KEYS_FILE" \
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

compose() {
  scripts/compose.sh "$@"
}

compose down --remove-orphans
compose build forge recon
compose up -d --remove-orphans --force-recreate \
  --wait --wait-timeout 300 forge recon

{
  printf 'forge %s\n' \
    "$(compose exec -T forge \
      cat /ssh-host-keys/ssh_host_ed25519_key.pub)"
  printf 'recon %s\n' \
    "$(compose exec -T recon \
      cat /ssh-host-keys/ssh_host_ed25519_key.pub)"
} > "$BARBAROSSA_KNOWN_HOSTS_FILE"
chmod 0644 "$BARBAROSSA_KNOWN_HOSTS_FILE"

compose up -d --remove-orphans --force-recreate \
  --wait --wait-timeout 300 hermes
BARBAROSSA_RUNTIME_DIR="$runtime" scripts/smoke-remote.sh
