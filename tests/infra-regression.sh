#!/bin/sh
set -eu

root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$root"

python3 - <<'PY'
from pathlib import Path

import yaml

compose = yaml.safe_load(Path("docker-compose.yml").read_text())
services = compose["services"]
assert set(services) == {"hermes", "forge", "recon"}
assert all("container_name" not in service for service in services.values())
assert all("healthcheck" in service for service in services.values())
assert all("mem_limit" in service for service in services.values())
assert all("pids_limit" in service for service in services.values())
assert all(service["logging"]["options"] == {
    "max-size": "10m", "max-file": "3"
} for service in services.values())
assert all(
    "no-new-privileges:true" in service["security_opt"]
    for service in services.values()
)
assert services["forge"]["mem_limit"] == "${BARBAROSSA_FORGE_MEMORY:-1408m}"
assert services["recon"]["mem_limit"] == "${BARBAROSSA_RECON_MEMORY:-640m}"
assert services["hermes"]["mem_limit"] == "${BARBAROSSA_HERMES_MEMORY:-1024m}"
assert "/opt/barbarossa/gateway_entrypoint.py" in " ".join(
    services["hermes"]["command"]
)
assert any(
    "/opt/barbarossa/gateway_entrypoint.py:ro" in volume
    for volume in services["hermes"]["volumes"]
)
assert any(
    "/etc/cont-init.d/016-barbarossa-secrets:ro" in volume
    for volume in services["hermes"]["volumes"]
)
assert services["hermes"]["environment"]["BARBAROSSA_SSH_KEY"] == (
    "/run/barbarossa-secrets/worker_key"
)
assert services["forge"]["networks"] == ["hermes-forge"]
assert services["recon"]["networks"] == ["hermes-recon"]
assert set(services["hermes"]["networks"]) == {
    "hermes-forge", "hermes-recon"
}
assert "ports" not in services["forge"]
assert "ports" not in services["recon"]
assert services["forge"]["read_only"] is True
assert services["recon"]["read_only"] is True
assert any(
    "forge-home:/home/forge" in volume
    for volume in services["forge"]["volumes"]
)
assert any(
    "forge-codex-home:/home/forge/.codex" in volume
    for volume in services["forge"]["volumes"]
)
assert services["hermes"]["env_file"] == [
    "${BARBAROSSA_HERMES_ENV_FILE:?set BARBAROSSA_HERMES_ENV_FILE}"
]
assert "DEEPSEEK_API_KEY" not in services["hermes"]["environment"]
assert all(
    "/var/run/docker.sock" not in str(service)
    for service in services.values()
)
assert services["hermes"]["image"] == (
    "nousresearch/hermes-agent@sha256:"
    "2fd023efbb8d3d2b0ce1a73d028b07370cff34f567cfe0e999553e8c327ea283"
)
volumes = compose["volumes"]
assert {"forge-host-keys", "recon-host-keys"} <= set(volumes)
secrets = compose["secrets"]
assert set(secrets) == {
    "worker_private_key",
    "worker_authorized_keys",
    "worker_known_hosts",
    "codex_auth_json",
    "github_token",
    "gmail_user",
    "gmail_app_password",
}
forge_secrets = {
    secret["source"]: secret
    for secret in services["forge"]["secrets"]
    if isinstance(secret, dict)
}
for name in ("codex_auth_json", "github_token", "gmail_user", "gmail_app_password"):
    assert forge_secrets[name]["target"] == name
forge_environment = services["forge"]["environment"]
assert forge_environment["GH_TOKEN_FILE"] == (
    "/run/barbarossa-secrets/github_token"
)
assert forge_environment["CODEX_AUTH_JSON_FILE"] == (
    "/home/forge/.codex/auth.json"
)
assert forge_environment["GMAIL_USER_FILE"] == (
    "/run/barbarossa-secrets/gmail_user"
)
assert forge_environment["GMAIL_APP_PASSWORD_FILE"] == (
    "/run/barbarossa-secrets/gmail_app_password"
)
assert forge_environment["BARBAROSSA_OPENCODE_MODEL"] == (
    "${BARBAROSSA_OPENCODE_MODEL:-opencode/deepseek-v4.1-flash-free}"
)
assert forge_environment["BARBAROSSA_OPENCODE_VARIANT"] == (
    "${BARBAROSSA_OPENCODE_VARIANT:-high}"
)
assert any(
    "./config/opencode:/usr/local/share/barbarossa/opencode:ro" in volume
    for volume in services["forge"]["volumes"]
)
assert any(
    "/opt/barbarossa/context/skills/barbarossa-opencode:ro" in volume
    for volume in services["hermes"]["volumes"]
)

workflow_path = Path(".github/workflows/build-deploy.yml")
workflow = yaml.safe_load(workflow_path.read_text())
jobs = workflow["jobs"]
assert {"validate", "build-router", "build-workers", "deploy"} <= set(jobs)
assert jobs["deploy"]["needs"] == [
    "validate", "build-router", "build-workers"
]
workflow_text = workflow_path.read_text()
assert "barbarossa-router-bundle:${{ github.sha }}" in workflow_text
assert "barbarossa-forge" in workflow_text
assert "barbarossa-recon" in workflow_text
assert "OVH_HOST_KEY" in workflow_text
assert "StrictHostKeyChecking=yes" in workflow_text
assert "scripts/deploy-runtime-files.sh" in workflow_text
assert "scripts/smoke-remote.sh" in Path("scripts/deploy-runtime-files.sh").read_text()
assert "BARBAROSSA_GITHUB_TOKEN" in workflow_text
# Deploy-only triggers: no PR verification runs.
assert "pull_request:" not in workflow_text
assert "workflow_dispatch:" in workflow_text
assert '      - "v*"' in workflow_text
assert "branches: [main]" not in workflow_text
assert workflow_text.count(
    "startsWith(github.ref, 'refs/tags/v')"
) == 4
assert "gitleaks" not in workflow_text.lower()
for line in workflow_text.splitlines():
    if "uses:" in line:
        reference = line.split("uses:", 1)[1].strip().split()[0]
        assert "@" in reference
        revision = reference.rsplit("@", 1)[1]
        assert len(revision) == 40
        int(revision, 16)
PY

grep -Fq 'supports_parallel_tool_calls": True' config/hermes/configure.py
grep -Fq 'HERMES_MAX_CONCURRENT_CHILDREN' config/hermes/configure.py
grep -Fq 'HERMES_MAX_SPAWN_DEPTH' config/hermes/configure.py
grep -Fq 'HERMES_ORCHESTRATOR_ENABLED' config/hermes/configure.py
grep -Fq '"image_input_mode": "text"' config/hermes/configure.py
grep -Fq '"vision"' config/hermes/configure.py
if grep -Eq 'deepseek-(v4-flash|flash)' config/hermes/configure.py; then
  printf 'Hermes configurator still pins the reference model\n' >&2
  exit 1
fi
if grep -Eq 'gpt-5\.6|luna|model_reasoning_effort' \
  config/codex/config.toml; then
  printf 'base Codex config still pins a deployment profile\n' >&2
  exit 1
fi
grep -Fq 'BARBAROSSA_SSH_KEY' config/hermes/configure.py
grep -Fq 'BARBAROSSA_KNOWN_HOSTS' config/hermes/configure.py
grep -Fq 'BARBAROSSA_STATE_DB' config/hermes/configure.py
grep -Fq 'BARBAROSSA_INPUT_ROOT' config/hermes/configure.py
grep -Fq 'BARBAROSSA_RESULT_ROOT' config/hermes/configure.py

for forbidden in \
  container_name \
  StrictHostKeyChecking=no \
  TERMINAL_SSH_USER=root \
  barbarossa-charlie \
  barbarossa-oscar \
  barbarossa-papa; do
  if grep -R -Fq "$forbidden" \
    docker-compose.yml AGENTS.md WORKERS.md config skills containers; then
    printf 'forbidden legacy pattern: %s\n' "$forbidden" >&2
    exit 1
  fi
done

grep -Fq 'router/.venv/' .gitignore
grep -Fq 'install -d -o forge -g forge -m 0700 /run/barbarossa-secrets' \
  containers/forge/forge-entrypoint.sh
grep -Fq 'for secret in github_token gmail_user gmail_app_password; do' \
  containers/forge/forge-entrypoint.sh
grep -Fq 'uv tool install' containers/forge/Dockerfile
grep -Fq 'specify-cli' containers/forge/Dockerfile
grep -Fq 'SPECIFY_REVISION' containers/forge/Dockerfile
if grep -Fq 'uv tool install' containers/forge/forge-entrypoint.sh; then
  printf 'Forge entrypoint must not install tools at boot\n' >&2
  exit 1
fi
grep -Fq 'home/forge/.local/bin' \
  config/codex/config.toml
grep -Fq 'vercel@${VERCEL_VERSION}' containers/forge/Dockerfile
grep -Fq 'supabase@${SUPABASE_VERSION}' containers/forge/Dockerfile
grep -Fq 'OPENCODE_VERSION=2.0.31' containers/forge/Dockerfile
grep -Fq '@opencode/cli@${OPENCODE_VERSION}' containers/forge/Dockerfile
grep -Fq -e '--allow-scripts=@opencode/cli' containers/forge/Dockerfile
grep -Fq 'opencode --version' containers/forge/Dockerfile
grep -Fq 'config/opencode' containers/forge/Dockerfile
grep -Fq 'astral-sh/uv/releases/download' containers/forge/Dockerfile
grep -Fq 'sha256sum -c -' containers/forge/Dockerfile
grep -Fq '"/run/barbarossa-secrets/$secret"' \
  containers/forge/forge-entrypoint.sh
grep -Fq '### Required two-step confirmation' \
  skills/hermes/barbarossa-gmail/SKILL.md
grep -Fq 'Never call `gmail_send` on the first request' \
  skills/hermes/barbarossa-gmail/SKILL.md
grep -Fq 'A changed recipient, subject, or body invalidates the prior confirmation' \
  skills/hermes/barbarossa-gmail/SKILL.md
grep -Fq \
  'auth_source="${CODEX_AUTH_SOURCE_FILE:-/run/secrets/codex_auth_json}"' \
  containers/forge/forge-entrypoint.sh
grep -Fq \
  'auth_target="${CODEX_AUTH_JSON_FILE:-/home/forge/.codex/auth.json}"' \
  containers/forge/forge-entrypoint.sh
grep -Fq 'refresh_is_newer' containers/forge/forge-entrypoint.sh
grep -Fq 'last_refresh' containers/forge/forge-entrypoint.sh
grep -Fq 'session_environment="SetEnv=\' \
  containers/forge/forge-entrypoint.sh
grep -Fq 'BARBAROSSA_CODEX_MODEL=$codex_model' \
  containers/forge/forge-entrypoint.sh
grep -Fq 'BARBAROSSA_OPENCODE_MODEL=$opencode_model' \
  containers/forge/forge-entrypoint.sh
grep -Fq 'BARBAROSSA_OPENCODE_VARIANT=$opencode_variant' \
  containers/forge/forge-entrypoint.sh
grep -Fq 'code_opencode' skills/hermes/barbarossa-opencode/SKILL.md
grep -Fq 'code.opencode' scripts/smoke-remote.sh
grep -Fq 'code.opencode' router/src/barbarossa_router/models.py
grep -Fq 'stage_opencode_config' containers/shared/worker-rpc.py
grep -Fq '"share": "disabled"' config/opencode/opencode.jsonc
# OpenCode v2 permission rules act on tool names (`edit`, `shell`, `subagent`);
# the v1 vocabulary (`bash`, `task`) is inert in agent frontmatter.
grep -Fq 'action: subagent' config/opencode/agents/orchestrator.md
grep -Fq 'action: shell' config/opencode/agents/reviewer.md
if grep -rqE 'action: (bash|task)$' config/opencode/agents/; then
  printf 'inert OpenCode permission action found\n' >&2
  exit 1
fi
grep -Fq 'insufficient free space' scripts/deploy-runtime-files.sh
grep -Fq 'DockerRootDir' scripts/deploy-runtime-files.sh
grep -Fq 'BARBAROSSA_MIN_FREE_KB' scripts/deploy-runtime-files.sh
grep -Fq 'refusing to prune' scripts/prune-rollback-images.sh
if grep -Fq 'prune-rollback-images' scripts/deploy-runtime-files.sh; then
  printf 'prune helper must stay out of the deploy path\n' >&2
  exit 1
fi
grep -Fq 'exec /usr/local/bin/worker-entrypoint "$@" -o "$session_environment"' \
  containers/forge/forge-entrypoint.sh
grep -Fq 'router/dist/' .gitignore
grep -Fq '.runtime/' .gitignore
grep -Fq '.env*' .dockerignore
grep -Fq '!.env.example' .dockerignore
grep -Fq 'hermes.env' .gitignore
grep -Fq '!hermes.env.example' .dockerignore
grep -Fq 'router/.venv/' .dockerignore
grep -Fq 'export BARBAROSSA_GITHUB_TOKEN_FILE=' setup.sh
grep -Fq \
  'touch "$BARBAROSSA_CODEX_AUTH_FILE" "$BARBAROSSA_GITHUB_TOKEN_FILE"' \
  setup.sh
grep -Fq '"$BARBAROSSA_GITHUB_TOKEN_FILE"' setup.sh
grep -Fq 'ssh-keygen -q -t ed25519' scripts/deploy-runtime-files.sh
grep -Fq 'restrict,command="/usr/local/bin/worker-ssh-dispatch"' \
  scripts/deploy-runtime-files.sh
grep -Fq "BARBAROSSA_RUNTIME_DIR=" scripts/deploy-runtime-files.sh
grep -Fq 'restore_release()' scripts/deploy-runtime-files.sh
grep -Fq 'ghcr.io/uphiago/barbarossa-router-bundle' \
  scripts/deploy-runtime-files.sh
if grep -qE 'compose down|volume rm|image prune|prune_release_images' scripts/deploy-runtime-files.sh; then
  printf 'destructive cleanup found in update path\n' >&2
  exit 1
fi
grep -Fq 'scripts/compose.sh' setup.sh
grep -Fq 'scripts/compose.sh' scripts/smoke-remote.sh
grep -Fq 'runtime_override=' scripts/compose.sh
if grep -Fq '. "$hermes_env"' setup.sh; then
  printf 'setup executes hermes.env as shell code\n' >&2
  exit 1
fi
grep -Fq 'docker compose' .github/workflows/build-deploy.yml
if grep -Fq 'DEEPSEEK_API_KEY=validate' \
  .github/workflows/build-deploy.yml; then
  printf 'CI still requires the reference provider\n' >&2
  exit 1
fi
grep -Fq 'mcp test barbarossa' scripts/smoke-remote.sh
grep -Fq 'secret value from {name} found in container logs' \
  scripts/smoke-remote.sh
grep -Fq 'available but untested' skills/hermes/barbarossa-routing/SKILL.md
grep -Fq 'Do not use `skill_manage`' skills/hermes/barbarossa-routing/SKILL.md
grep -Fq 'Do not read artifacts directly' skills/hermes/barbarossa-codex/SKILL.md

for forbidden in StrictHostKeyChecking=no ssh-keyscan; do
  if grep -R -Fq "$forbidden" .github scripts; then
    printf 'unsafe deploy pattern: %s\n' "$forbidden" >&2
    exit 1
  fi
done

test ! -e workers
if grep -R -Eiq '\b(charlie|oscar|papa)\b' \
  docker-compose.yml README.md WORKERS.md AGENTS.md setup.sh; then
  printf 'legacy worker name remains in active infrastructure or docs\n' >&2
  exit 1
fi

# Prune helper drill: keeps the newest rollback release, removes stale release
# directories and the image tags that only they reference (docker is mocked;
# no daemon is involved).
(
  set -eu
  drill="$(mktemp -d)"
  trap 'rm -rf "$drill"' EXIT HUP INT TERM
  mkdir -p "$drill/bin" "$drill/runtime/rollback/release.AAA" \
    "$drill/runtime/rollback/release.BBB" "$drill/runtime/rollback/release.CCC"
  for release in AAA:2026-10-01 BBB:2026-10-08 CCC:2026-10-16; do
    name="${release%:*}"
    printf 'services:\n  forge:\n    image: barbarossa-rollback-forge:release.%s\n  hermes:\n    image: barbarossa-rollback-hermes:release.%s\n' \
      "$name" "$name" > "$drill/runtime/rollback/release.$name/images.yml"
    touch -d "${release#*:} 10:00" "$drill/runtime/rollback/release.$name"
  done
  cat > "$drill/bin/docker" <<'FAKE_DOCKER'
#!/bin/sh
state="${FAKE_STATE:?}"
if [ "$1" = "image" ] && [ "$2" = "inspect" ]; then
  ref="$5"
  id="$(awk -v r="$ref" '$2 == r { print $1 }' "$state")"
  [ -n "$id" ] || exit 1
  printf '%s\n' "$id"
  exit 0
fi
case "$1" in
  images) awk '{ print $1, $2 }' "$state" ;;
  rmi)
    shift
    for t in "$@"; do
      grep -v " $t\$" "$state" > "$state.new" || true
      mv "$state.new" "$state"
    done ;;
  info) printf '/\n' ;;
  *) exit 1 ;;
esac
FAKE_DOCKER
  chmod +x "$drill/bin/docker"
  cat > "$drill/state" <<'FAKE_STATE'
sha256:aaa barbarossa-rollback-forge:release.AAA
sha256:aaa ghcr.io/uphiago/barbarossa-forge:oldsha
sha256:bbb barbarossa-rollback-forge:release.BBB
sha256:ccc barbarossa-rollback-forge:release.CCC
sha256:ccc unrelated-org/img:keep
sha256:ccc barbarossa-rollback-hermes:release.AAA
sha256:ccc barbarossa-rollback-hermes:release.BBB
sha256:ccc barbarossa-rollback-hermes:release.CCC
FAKE_STATE
  touch "$drill/runtime/.deploy.lock"
  if FAKE_STATE="$drill/state" DOCKER="$drill/bin/docker" \
    BARBAROSSA_RUNTIME_DIR="$drill/runtime" \
    sh scripts/prune-rollback-images.sh >/dev/null 2>&1; then
    printf 'prune helper ignored the deploy lock\n' >&2
    exit 1
  fi
  rm -f "$drill/runtime/.deploy.lock"
  FAKE_STATE="$drill/state" DOCKER="$drill/bin/docker" \
    BARBAROSSA_RUNTIME_DIR="$drill/runtime" \
    sh scripts/prune-rollback-images.sh >/dev/null
  test -d "$drill/runtime/rollback/release.AAA"
  FAKE_STATE="$drill/state" DOCKER="$drill/bin/docker" \
    BARBAROSSA_RUNTIME_DIR="$drill/runtime" \
    sh scripts/prune-rollback-images.sh --apply >/dev/null
  test ! -d "$drill/runtime/rollback/release.AAA"
  test ! -d "$drill/runtime/rollback/release.BBB"
  test -d "$drill/runtime/rollback/release.CCC"
  grep -Fq 'release.CCC' "$drill/state"
  grep -Fq 'unrelated-org/img:keep' "$drill/state"
  if grep -Eq 'release\.(AAA|BBB)|oldsha' "$drill/state"; then
    printf 'prune helper leaked stale tags\n' >&2
    exit 1
  fi
)

printf 'all infra regression assertions passed\n'
