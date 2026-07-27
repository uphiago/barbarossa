#!/bin/bash
set -euo pipefail

SSH_DIR=/root/.ssh
AUTH_KEYS=$SSH_DIR/authorized_keys
KEY_MOUNT=/ssh-keys

if [ ! -f /etc/ssh/ssh_host_ed25519_key ]; then
    echo "[+] Generating SSH host keys..."
    ssh-keygen -A >/dev/null 2>&1
fi

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
