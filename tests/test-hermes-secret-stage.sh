#!/bin/sh
set -eu

root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
temporary="$(mktemp -d)"
trap 'rm -rf "$temporary"' EXIT HUP INT TERM
source_root="$temporary/source"
target_root="$temporary/target"
install -d -m 0700 "$source_root"
printf 'private-key\n' > "$source_root/worker_key"
printf 'known-host\n' > "$source_root/known_hosts"
chmod 0600 "$source_root/worker_key"
chmod 0644 "$source_root/known_hosts"

BARBAROSSA_SECRET_SOURCE_ROOT="$source_root" \
BARBAROSSA_SECRET_TARGET_ROOT="$target_root" \
BARBAROSSA_SECRET_OWNER="$(id -un)" \
BARBAROSSA_SECRET_GROUP="$(id -gn)" \
  "$root/containers/hermes/stage-secrets.sh"

test "$(stat -c %a "$target_root")" = 700
test "$(stat -c %a "$target_root/worker_key")" = 600
test "$(stat -c %a "$target_root/known_hosts")" = 644
test "$(cat "$target_root/worker_key")" = private-key
test "$(cat "$target_root/known_hosts")" = known-host
