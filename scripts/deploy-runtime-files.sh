#!/bin/sh
set -eu

root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
runtime="${BARBAROSSA_RUNTIME_DIR:-$HOME/.config/barbarossa/runtime}"
tag="${BARBAROSSA_IMAGE_TAG:?BARBAROSSA_IMAGE_TAG is required}"
docker="${DOCKER:-docker}"

install -d -m 0700 "$runtime"
umask 077

worker_key="$runtime/worker_key"
authorized_keys="$runtime/authorized_keys"
known_hosts="$runtime/known_hosts"
codex_token="$runtime/codex_access_token"
codex_auth="$runtime/codex_auth.json"
github_token="$runtime/github_token"
router_bundle="$runtime/barbarossa-router.pex"
compose_env="$runtime/compose.env"

touch "$codex_token" "$codex_auth" "$github_token"
if [ ! -s "$codex_token" ] && [ ! -s "$codex_auth" ]; then
  printf 'missing Codex access token or auth.json in %s\n' "$runtime" >&2
  exit 1
fi

rm -f "$worker_key" "$worker_key.pub" "$authorized_keys" "$known_hosts"
ssh-keygen -q -t ed25519 -N "" -C "hermes@barbarossa" -f "$worker_key"
printf 'restrict,command="/usr/local/bin/worker-ssh-dispatch" %s\n' \
  "$(cat "$worker_key.pub")" > "$authorized_keys"
chmod 0600 "$worker_key" "$codex_token" "$codex_auth" "$github_token"
chmod 0644 "$authorized_keys"

cat > "$compose_env" <<EOF
BARBAROSSA_IMAGE_TAG=$tag
BARBAROSSA_RUNTIME_DIR=$runtime
EOF
chmod 0600 "$compose_env"

compose() {
  "$docker" compose \
    --env-file "$root/.env" \
    --env-file "$compose_env" \
    -f "$root/docker-compose.yml" "$@"
}

compose down --remove-orphans
"$docker" rm -f charlie oscar papa hermes 2>/dev/null || true
"$docker" volume rm \
  barbarossa_charlie-data barbarossa_charlie-ssh \
  barbarossa_oscar-data barbarossa_oscar-ssh \
  barbarossa_papa-data barbarossa_papa-ssh barbarossa_papa-tor \
  barbarossa_hermes-data \
  2>/dev/null || true

"$docker" pull "ghcr.io/uphiago/barbarossa-router-bundle:$tag"
bundle_container="barbarossa-router-bundle-$$"
"$docker" create --name "$bundle_container" \
  "ghcr.io/uphiago/barbarossa-router-bundle:$tag" \
  /barbarossa-router.pex >/dev/null
trap '"$docker" rm -f "$bundle_container" >/dev/null 2>&1 || true' EXIT HUP INT TERM
"$docker" cp "$bundle_container:/barbarossa-router.pex" "$router_bundle"
"$docker" rm "$bundle_container" >/dev/null
trap - EXIT HUP INT TERM
chmod 0555 "$router_bundle"

compose pull forge recon
compose up -d --remove-orphans --force-recreate --wait --wait-timeout 300 \
  forge recon

{
  printf 'forge %s\n' \
    "$(compose exec -T forge cat /ssh-host-keys/ssh_host_ed25519_key.pub)"
  printf 'recon %s\n' \
    "$(compose exec -T recon cat /ssh-host-keys/ssh_host_ed25519_key.pub)"
} > "$known_hosts"
chmod 0644 "$known_hosts"

compose up -d --remove-orphans --force-recreate --wait --wait-timeout 300 \
  hermes
"$docker" image prune -f >/dev/null
