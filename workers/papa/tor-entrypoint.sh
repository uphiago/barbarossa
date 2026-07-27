#!/usr/bin/env bash
set -euo pipefail

tor_pid=
sshd_pid=

terminate() {
    [ -z "$tor_pid" ] || kill "$tor_pid" 2>/dev/null || true
    [ -z "$sshd_pid" ] || kill "$sshd_pid" 2>/dev/null || true
}
trap terminate EXIT INT TERM

tor -f /etc/tor/torrc &
tor_pid=$!

for _ in $(seq 1 45); do
    kill -0 "$tor_pid" 2>/dev/null || {
        wait "$tor_pid"
        exit $?
    }
    nc -z 127.0.0.1 9050 2>/dev/null && break
    sleep 1
done

if ! nc -z 127.0.0.1 9050 2>/dev/null; then
    echo "Tor SOCKS listener did not become ready" >&2
    exit 1
fi

echo "Tor SOCKS5 ready on :9050"
"$@" &
sshd_pid=$!

set +e
wait -n "$tor_pid" "$sshd_pid"
rc=$?
set -e

echo "Tor or SSH exited unexpectedly" >&2
exit "$rc"
