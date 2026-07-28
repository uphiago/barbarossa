#!/bin/sh
set -eu

tor_pid=
service_pid=

terminate() {
  [ -z "$tor_pid" ] || kill "$tor_pid" 2>/dev/null || true
  [ -z "$service_pid" ] || kill "$service_pid" 2>/dev/null || true
}
trap terminate EXIT INT TERM

tor -f /etc/tor/torrc &
tor_pid=$!

ready=false
for _ in $(seq 1 45); do
  if ! kill -0 "$tor_pid" 2>/dev/null; then
    wait "$tor_pid"
    exit $?
  fi
  if nc -z 127.0.0.1 9050 2>/dev/null; then
    ready=true
    break
  fi
  sleep 1
done

if [ "$ready" != true ]; then
  printf 'Tor SOCKS listener did not become ready\n' >&2
  exit 1
fi

"$@" &
service_pid=$!

set +e
wait -n "$tor_pid" "$service_pid"
status=$?
set -e

printf 'Tor or worker service exited unexpectedly\n' >&2
exit "$status"
