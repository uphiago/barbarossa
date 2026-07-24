#!/bin/bash

SSH_DIR=/root/.ssh
AUTH_KEYS=$SSH_DIR/authorized_keys
KEY_MOUNT=/ssh-keys

# Generate SSH host keys if missing
if [ ! -f /etc/ssh/ssh_host_rsa_key ]; then
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
    echo "[+] SSH keys found, access configured"
    wc -l "$AUTH_KEYS"
else
    echo "[!] WARNING: No SSH keys found!"
    echo "[!] Mount a volume with your public key: -v ~/.ssh/authorized_keys:/ssh-keys/authorized_keys"
fi

echo "[+] Starting SSHD..."
exec "$@"
