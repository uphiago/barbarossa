#!/bin/bash
set -euo pipefail

SSH_DIR=/root/.ssh
AUTH_KEYS=$SSH_DIR/authorized_keys
KEY_MOUNT=/ssh-keys
HOST_KEYS_DIR=/ssh-host-keys

mkdir -p "$HOST_KEYS_DIR"
if [ ! -f "$HOST_KEYS_DIR/ssh_host_ed25519_key" ]; then
    echo "[+] Generating SSH host keys..."
    ssh-keygen -q -t ed25519 -N "" \
        -f "$HOST_KEYS_DIR/ssh_host_ed25519_key"
fi
chmod 600 "$HOST_KEYS_DIR/ssh_host_ed25519_key"
chmod 644 "$HOST_KEYS_DIR/ssh_host_ed25519_key.pub"
ln -sf "$HOST_KEYS_DIR/ssh_host_ed25519_key" \
    /etc/ssh/ssh_host_ed25519_key
ln -sf "$HOST_KEYS_DIR/ssh_host_ed25519_key.pub" \
    /etc/ssh/ssh_host_ed25519_key.pub

if [ -d "$KEY_MOUNT" ]; then
    echo "[+] Copying authorized_keys from $KEY_MOUNT"
    if [ -f "$KEY_MOUNT/authorized_keys" ]; then
        cp "$KEY_MOUNT/authorized_keys" "$AUTH_KEYS"
    else
        cat "$KEY_MOUNT"/*.pub >> "$AUTH_KEYS" 2>/dev/null || true
    fi
    chmod 600 "$AUTH_KEYS"
fi

if [ -f "$AUTH_KEYS" ]; then
    echo "[+] SSH keys found ($(wc -l < $AUTH_KEYS) keys), access configured"
else
    echo "[!] No SSH authorized keys found; refusing to start." >&2
    exit 1
fi

echo "[+] Starting SSHD..."
exec "$@"
