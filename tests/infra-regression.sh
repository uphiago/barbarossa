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
if [ "$healthchecks" -eq 4 ]; then
    pass "all services define healthchecks"
else
    fail "all services define healthchecks"
fi

contains "Hermes waits for healthy workers" docker-compose.yml \
    'condition: service_healthy'
for worker in charlie oscar papa; do
    contains "$worker persists SSH host keys" docker-compose.yml \
        "${worker}-ssh:/ssh-host-keys"
    contains "$worker image does not ship SSH host keys" \
        "workers/$worker/Dockerfile" 'rm -f /etc/ssh/ssh_host_\*'
done
contains "worker entrypoint uses the dedicated host-key directory" \
    workers/shared/worker-entrypoint.sh 'HOST_KEYS_DIR=/ssh-host-keys'
contains "worker entrypoint links the persisted host key" \
    workers/shared/worker-entrypoint.sh \
    'ln -sf "\$HOST_KEYS_DIR/ssh_host_ed25519_key"'

contains "Tor entrypoint traps termination" workers/papa/tor-entrypoint.sh \
    '^trap .*TERM'
contains "Tor entrypoint supervises children" workers/papa/tor-entrypoint.sh \
    'wait -n'
contains "Tor health uses remote DNS through SOCKS" docker-compose.yml \
    '--socks5-hostname'
contains "Papa persists Tor state" docker-compose.yml \
    'papa-tor:/var/lib/tor'

logging_blocks=$(grep -c '^    logging:' docker-compose.yml || true)
if [ "$logging_blocks" -eq 4 ]; then
    pass "all services bound Docker logs"
else
    fail "all services bound Docker logs"
fi

pids_limits=$(grep -c '^    pids_limit:' docker-compose.yml || true)
if [ "$pids_limits" -eq 4 ]; then
    pass "all services define PID limits"
else
    fail "all services define PID limits"
fi

memory_limits=$(grep -c '^    mem_limit:' docker-compose.yml || true)
if [ "$memory_limits" -eq 4 ]; then
    pass "all services define memory limits"
else
    fail "all services define memory limits"
fi

no_new_privileges=$(grep -c '^      - no-new-privileges:true$' \
    docker-compose.yml || true)
if [ "$no_new_privileges" -eq 4 ]; then
    pass "all services prevent privilege escalation"
else
    fail "all services prevent privilege escalation"
fi

max_log_sizes=$(grep -c '^        max-size: "10m"$' docker-compose.yml || true)
max_log_files=$(grep -c '^        max-file: "3"$' docker-compose.yml || true)
if [ "$max_log_sizes" -eq 4 ] && [ "$max_log_files" -eq 4 ]; then
    pass "all services rotate Docker logs"
else
    fail "all services rotate Docker logs"
fi

contains "production workflow receives worker key secret" \
    .github/workflows/build-deploy.yml 'BARBAROSSA_WORKER_SSH_KEY_B64'
absent "workflow actions are pinned to immutable commits" \
    .github/workflows/build-deploy.yml \
    'uses: [A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@v[0-9]'
contains "checkout is pinned" .github/workflows/build-deploy.yml \
    'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1'
contains "paths-filter is pinned" .github/workflows/build-deploy.yml \
    'dorny/paths-filter@7b450fff21473bca461d4b92ce414b9d0420d706'
contains "registry login is pinned" .github/workflows/build-deploy.yml \
    'docker/login-action@abd2ef45e78c5afb21d64d4ca52ee8550d9572c7'
contains "container build is pinned" .github/workflows/build-deploy.yml \
    'docker/build-push-action@53b7df96c91f9c12dcc8a07bcb9ccacbed38856a'
contains "SSH deploy is pinned" .github/workflows/build-deploy.yml \
    'appleboy/ssh-action@0ff4204d59e8e51228ff73bce53f80d53301dee2'
absent "repository clone never embeds a GitHub token" \
    .github/workflows/build-deploy.yml 'x-access-token'
contains "production clone uses the public repository URL" \
    .github/workflows/build-deploy.yml \
    'git clone https://github\.com/uphiago/barbarossa\.git'
contains "production resets origin to the public repository URL" \
    .github/workflows/build-deploy.yml \
    'git remote set-url origin https://github\.com/uphiago/barbarossa\.git'
contains "production pulls main with fast-forward only" \
    .github/workflows/build-deploy.yml \
    'git pull --ff-only origin main'
contains "registry authentication uses a temporary Docker config" \
    .github/workflows/build-deploy.yml 'DOCKER_AUTH_DIR=\$\(mktemp -d\)'
contains "registry authentication is removed on exit" \
    .github/workflows/build-deploy.yml \
    'rm -rf "\$DOCKER_AUTH_DIR"'
contains "production workflow supports manual key rotation" \
    .github/workflows/build-deploy.yml '^  workflow_dispatch:'
contains "production workflow validates worker private key" \
    .github/workflows/build-deploy.yml 'ssh-keygen -y'
absent "production worker key secret is optional" \
    .github/workflows/build-deploy.yml \
    'Missing BARBAROSSA_WORKER_SSH_KEY_B64 GitHub secret'
contains "README documents optional production key rotation" README.md \
    'The optional'
absent "README does not require a production key secret" README.md \
    'requires the base64-encoded private worker key'
contains "production can reuse the active Hermes key" \
    .github/workflows/build-deploy.yml \
    '\$DOCKER exec hermes cat /opt/data/ssh/key'
contains "failed active-key reads remove the empty candidate" \
    .github/workflows/build-deploy.yml \
    'rm -f "\$WORKER_KEY\.next"$'
contains "production key rotation has a transition file" \
    .github/workflows/build-deploy.yml 'AUTHORIZED_KEYS\.transition'
contains "production updates authorized keys in place" \
    .github/workflows/build-deploy.yml \
    'cat "\$AUTHORIZED_KEYS\.transition" > "\$AUTHORIZED_KEYS"'
contains "production recreates workers for key transition" \
    .github/workflows/build-deploy.yml \
    '--force-recreate'
contains "production waits for worker health" \
    .github/workflows/build-deploy.yml \
    '--wait --wait-timeout [0-9]+ charlie oscar papa'
contains "production tests the candidate key before promotion" \
    .github/workflows/build-deploy.yml \
    'ssh -i /opt/data/ssh/key\.next'
contains "production tests every worker" \
    .github/workflows/build-deploy.yml \
    'for host in charlie oscar papa'
contains "production installs the candidate key into Hermes" \
    .github/workflows/build-deploy.yml \
    '\$DOCKER cp "\$WORKER_KEY\.next" hermes:/opt/data/ssh/key\.next'

for dockerfile in workers/charlie/Dockerfile workers/oscar/Dockerfile; do
    contains "$dockerfile verifies archive checksums" "$dockerfile" \
        'sha256sum -c'
    absent "$dockerfile has no mutable Amass download" "$dockerfile" \
        '/releases/latest/'
done
absent "Oscar does not hide pip failures" workers/oscar/Dockerfile \
    '2>/dev/null \|\| true'

contains "Docker build context excludes environment files" .dockerignore \
    '^\.env\*$'
contains "Docker build context keeps the environment example" .dockerignore \
    '^!\.env\.example$'
contains "Docker build context excludes SSH keys" .dockerignore \
    '^worker/ssh-keys/$'
contains "Git excludes private key files" .gitignore \
    '^\*\.key$'
contains "Git excludes PEM files" .gitignore \
    '^\*\.pem$'
contains "Git excludes environment variants" .gitignore \
    '^\.env\.\*$'
contains "secret scan downloads a pinned Gitleaks version" \
    .github/workflows/secret-scan.yml \
    'GITLEAKS_VERSION: 8\.30\.1'
contains "secret scan verifies the Gitleaks archive" \
    .github/workflows/secret-scan.yml \
    '551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb'
contains "secret scan checks the complete Git history" \
    .github/workflows/secret-scan.yml \
    'fetch-depth: 0'
contains "pre-commit uses the pinned Gitleaks release" \
    .pre-commit-config.yaml \
    'rev: v8\.30\.1'
contains "Gitleaks ignores only the reviewed healthcheck false positive" \
    .gitleaksignore \
    '^2e050bd85cc232c19f2e9d4bde5d3d5612b4cc61:docker-compose\.yml:curl-auth-user:163$'
absent "README omits private rollback paths" README.md \
    'barbarossa-hardening-backup|\.local/state/barbarossa/backups'

for private_doc in \
    docs/superpowers/plans/2026-07-27-infra-consolidation.md \
    docs/superpowers/plans/2026-07-27-ovh-hardening.md \
    docs/superpowers/specs/2026-07-27-infra-consolidation-design.md; do
    if [ ! -e "$private_doc" ]; then
        pass "$private_doc is outside the public tree"
    else
        fail "$private_doc is outside the public tree"
    fi
done

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
