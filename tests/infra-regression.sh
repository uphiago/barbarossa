#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

failures=0

pass() {
    printf 'ok   %s\n' "$1"
}

fail() {
    printf 'FAIL %s\n' "$1" >&2
    failures=$((failures + 1))
}

contains() {
    local description=$1 file=$2 pattern=$3
    if grep -Eq -- "$pattern" "$file"; then
        pass "$description"
    else
        fail "$description"
    fi
}

absent() {
    local description=$1 file=$2 pattern=$3
    if grep -Eq -- "$pattern" "$file"; then
        fail "$description"
    else
        pass "$description"
    fi
}

contains "authorized keys path is external" docker-compose.yml \
    'BARBAROSSA_AUTHORIZED_KEYS_FILE:\?'
contains "dashboard user is required" docker-compose.yml \
    'DASHBOARD_USER:\?'
contains "dashboard password is required" docker-compose.yml \
    'DASHBOARD_PASS:\?'
contains "dashboard secret is required" docker-compose.yml \
    'DASHBOARD_SECRET:\?'
absent "dashboard has no weak password fallback" docker-compose.yml \
    'DASHBOARD_PASS:-barbarossa'
absent "dashboard has no weak signing-secret fallback" docker-compose.yml \
    'barbarossa-dashboard-secret-change-me'

healthchecks=$(grep -c '^    healthcheck:' docker-compose.yml || true)
if [ "$healthchecks" -eq 3 ]; then
    pass "all workers define healthchecks"
else
    fail "all workers define healthchecks"
fi

contains "Hermes waits for healthy workers" docker-compose.yml \
    'condition: service_healthy'
for worker in charlie oscar papa; do
    contains "$worker persists SSH host keys" docker-compose.yml \
        "${worker}-ssh:/etc/ssh"
done

contains "Tor entrypoint traps termination" workers/papa/tor-entrypoint.sh \
    '^trap .*TERM'
contains "Tor entrypoint supervises children" workers/papa/tor-entrypoint.sh \
    'wait -n'
contains "Tor health uses remote DNS through SOCKS" docker-compose.yml \
    '--socks5-hostname'

contains "production workflow receives worker key secret" \
    .github/workflows/build-deploy.yml 'BARBAROSSA_WORKER_SSH_KEY_B64'
contains "production workflow validates worker private key" \
    .github/workflows/build-deploy.yml 'ssh-keygen -y'

for dockerfile in workers/charlie/Dockerfile workers/oscar/Dockerfile; do
    contains "$dockerfile verifies archive checksums" "$dockerfile" \
        'sha256sum -c'
    absent "$dockerfile has no mutable Amass download" "$dockerfile" \
        '/releases/latest/'
done
absent "Oscar does not hide pip failures" workers/oscar/Dockerfile \
    '2>/dev/null \|\| true'

if [ ! -e ../images ] && [ ! -e ../compose ]; then
    pass "obsolete worker infrastructure is absent"
else
    fail "obsolete worker infrastructure is absent"
fi

if [ "$failures" -ne 0 ]; then
    printf '\n%d regression assertion(s) failed\n' "$failures" >&2
    exit 1
fi

printf '\nall infra regression assertions passed\n'
