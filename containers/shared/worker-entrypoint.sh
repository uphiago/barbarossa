#!/bin/sh
set -eu

: "${WORKER_USER:?WORKER_USER is required}"

worker_home="$(getent passwd "$WORKER_USER" | cut -d: -f6)"
if [ -z "$worker_home" ]; then
  printf 'unknown worker user: %s\n' "$WORKER_USER" >&2
  exit 1
fi

install -d -m 0700 /ssh-host-keys
if [ ! -f /ssh-host-keys/ssh_host_ed25519_key ]; then
  ssh-keygen -q -t ed25519 -N '' \
    -f /ssh-host-keys/ssh_host_ed25519_key
fi
chmod 0600 /ssh-host-keys/ssh_host_ed25519_key
chmod 0644 /ssh-host-keys/ssh_host_ed25519_key.pub

install -d -o "$WORKER_USER" -g "$WORKER_USER" -m 0700 \
  "$worker_home/.ssh"
install -o "$WORKER_USER" -g "$WORKER_USER" -m 0600 \
  "${AUTHORIZED_KEYS_FILE:-/run/secrets/worker_authorized_keys}" \
  "$worker_home/.ssh/authorized_keys"

install -d -o "$WORKER_USER" -g "$WORKER_USER" -m 0700 \
  /workspace /workspace/jobs /workspace/.locks
chown -R "$WORKER_USER:$WORKER_USER" /workspace

exec "$@"
