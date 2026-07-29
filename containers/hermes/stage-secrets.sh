#!/bin/sh
set -eu

source_root="${BARBAROSSA_SECRET_SOURCE_ROOT:-/run/secrets}"
target_root="${BARBAROSSA_SECRET_TARGET_ROOT:-/run/barbarossa-secrets}"
owner="${BARBAROSSA_SECRET_OWNER:-hermes}"
group="${BARBAROSSA_SECRET_GROUP:-hermes}"

install -d -o "$owner" -g "$group" -m 0700 "$target_root"
install -o "$owner" -g "$group" -m 0600 \
  "$source_root/worker_key" "$target_root/worker_key"
install -o "$owner" -g "$group" -m 0644 \
  "$source_root/known_hosts" "$target_root/known_hosts"
