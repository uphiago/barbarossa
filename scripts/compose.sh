#!/bin/sh
set -eu

root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
docker="${DOCKER:-docker}"

test -f "$root/.env" || {
  printf 'missing %s/.env\n' "$root" >&2
  exit 1
}

runtime_override="${BARBAROSSA_RUNTIME_DIR:-}"
set -a
# shellcheck disable=SC1091
. "$root/.env"
set +a

runtime="${runtime_override:-${BARBAROSSA_RUNTIME_DIR:-$root/.runtime}}"
case "$runtime" in
  /*) ;;
  *) runtime="$root/${runtime#./}" ;;
esac

if [ -f "$runtime/compose.env" ]; then
  exec "$docker" compose \
    --env-file "$root/.env" \
    --env-file "$runtime/compose.env" \
    -f "$root/docker-compose.yml" "$@"
fi

exec "$docker" compose \
  --env-file "$root/.env" \
  -f "$root/docker-compose.yml" "$@"
