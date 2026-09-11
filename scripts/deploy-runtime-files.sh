#!/bin/sh
set -eu

root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
runtime="${BARBAROSSA_RUNTIME_DIR:-$HOME/.config/barbarossa/runtime}"
tag="${BARBAROSSA_IMAGE_TAG:?BARBAROSSA_IMAGE_TAG is required}"
docker="${DOCKER:-docker}"

# The release tag is data in a dotenv file and a Docker image reference.
case "$tag" in
  [A-Za-z0-9_]*) ;;
  *) printf 'invalid image tag\n' >&2; exit 1 ;;
esac
case "$tag" in
  *[!A-Za-z0-9_.-]*) printf 'invalid image tag\n' >&2; exit 1 ;;
esac
[ "${#tag}" -le 128 ] || { printf 'invalid image tag\n' >&2; exit 1; }
case "$runtime" in
  /*) ;;
  *) runtime="$root/${runtime#./}" ;;
esac
case "$runtime" in
  *"'"*|*'
'*) printf 'unsupported runtime path\n' >&2; exit 1 ;;
esac
[ -f "$root/.env" ] || { printf 'missing .env\n' >&2; exit 1; }

umask 077
install -d -m 0700 "$runtime"
lock="$runtime/.deploy.lock"
if ! mkdir "$lock" 2>/dev/null; then
  printf 'deployment lock exists: %s (check for an active deployment)\n' "$lock" >&2
  exit 1
fi
stage=""
bundle_container=""
rollback=""
committed=0
complete=0
mode=bootstrap
worker_key="$runtime/worker_key"
authorized_keys="$runtime/authorized_keys"
known_hosts="$runtime/known_hosts"
router_bundle="$runtime/barbarossa-router.pex"
compose_env="$runtime/compose.env"

compose_with_env() (
  release_env="$1"
  shift
  # Shell variables override --env-file; they must not defeat a rollback.
  unset BARBAROSSA_IMAGE_TAG BARBAROSSA_RUNTIME_DIR
  "$docker" compose \
    --env-file "$root/.env" \
    --env-file "$release_env" \
    -f "$root/docker-compose.yml" "$@"
)

restore_release() {
  printf 'deployment failed; restoring rollback release %s\n' "$rollback" >&2
  # Rename new inodes into place, then recreate containers to renew bind mounts.
  # Never truncate files still mounted read-only by a running Hermes container.
  if ! cp -p "$rollback/compose.env" "$stage/restore.env" ||
    ! cp -p "$rollback/barbarossa-router.pex" "$stage/restore.pex" ||
    ! mv -f "$stage/restore.env" "$compose_env" ||
    ! mv -f "$stage/restore.pex" "$router_bundle"; then
    printf 'rollback file restore failed; retained release: %s\n' "$rollback" >&2
    return 1
  fi
  if (
    unset BARBAROSSA_IMAGE_TAG BARBAROSSA_RUNTIME_DIR
    "$docker" compose --env-file "$compose_env" \
      -f "$rollback/compose.json" -f "$rollback/images.yml" \
      up -d --no-build --pull never --force-recreate --wait --wait-timeout 300 \
      forge recon hermes
  ); then
    printf 'rolled-back\n' > "$rollback/status"
    printf 'rollback startup succeeded\n' >&2
  else
    printf 'rollback-failed\n' > "$rollback/status"
    printf 'rollback startup failed; retained files and images: %s\n' "$rollback" >&2
    return 1
  fi
}

cleanup() {
  result=$?
  trap - EXIT HUP INT TERM
  if [ "$committed" -eq 1 ] && [ "$complete" -eq 0 ]; then
    if [ "$mode" = update ]; then
      restore_release || true
    else
      printf 'bootstrap startup failed; credentials and generated keys retained in %s\n' "$runtime" >&2
    fi
    [ "$result" -ne 0 ] || result=1
  fi
  if [ -n "$bundle_container" ]; then
    "$docker" rm -f "$bundle_container" >/dev/null 2>&1 || true
  fi
  [ -z "$stage" ] || rm -rf -- "$stage"
  rmdir "$lock" 2>/dev/null || true
  exit "$result"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
stage="$(mktemp -d "$runtime/.deploy.XXXXXXXX")"

for credential in codex_auth.json gmail_app_password; do
  [ -s "$runtime/$credential" ] || {
    printf 'missing %s in %s\n' "$credential" "$runtime" >&2
    exit 1
  }
done

# Bootstrap is allowed only without any prior deployment material. Never rotate
# a key to repair a partial install; that could strand the running workers.
for filename in worker_key worker_key.pub authorized_keys known_hosts compose.env barbarossa-router.pex; do
  if [ -e "$runtime/$filename" ] || [ -L "$runtime/$filename" ]; then
    mode=update
  fi
done
if [ "$mode" = update ]; then
  for filename in worker_key worker_key.pub authorized_keys known_hosts compose.env barbarossa-router.pex; do
    if [ ! -s "$runtime/$filename" ] || [ ! -f "$runtime/$filename" ] || [ -L "$runtime/$filename" ]; then
      printf 'incomplete existing install: %s; restore the prior release before updating\n' "$filename" >&2
      exit 1
    fi
  done
  # Validate the private/public/authorized relationship without printing keys.
  ssh-keygen -y -P '' -f "$worker_key" > "$stage/public-key.raw"
  awk '{print $1, $2}' "$stage/public-key.raw" > "$stage/public-key"
  awk '{print $1, $2}' "$worker_key.pub" > "$stage/expected-key"
  cmp -s "$stage/public-key" "$stage/expected-key" || {
    printf 'worker key pair does not match\n' >&2
    exit 1
  }
  printf 'restrict,command="/usr/local/bin/worker-ssh-dispatch" %s\n' \
    "$(cat "$worker_key.pub")" > "$stage/authorized_keys"
  cmp -s "$stage/authorized_keys" "$authorized_keys" || {
    printf 'worker authorized key does not match the restricted worker key\n' >&2
    exit 1
  }
fi

cat > "$stage/compose.env" <<EOF_ENV
BARBAROSSA_IMAGE_TAG=$tag
BARBAROSSA_RUNTIME_DIR='$runtime'
EOF_ENV

# Download and extract everything before changing runtime files or services.
compose_with_env "$stage/compose.env" pull forge recon hermes
"$docker" pull "ghcr.io/uphiago/barbarossa-router-bundle:$tag"
bundle_container="barbarossa-router-bundle-${stage##*.}"
"$docker" create --name "$bundle_container" \
  "ghcr.io/uphiago/barbarossa-router-bundle:$tag" \
  /barbarossa-router.pex >/dev/null
"$docker" cp "$bundle_container:/barbarossa-router.pex" "$stage/barbarossa-router.pex"
"$docker" rm "$bundle_container" >/dev/null
bundle_container=""
[ -s "$stage/barbarossa-router.pex" ] || { printf 'empty router bundle\n' >&2; exit 1; }
chmod 0555 "$stage/barbarossa-router.pex"

if [ "$mode" = update ]; then
  install -d -m 0700 "$runtime/rollback"
  rollback="$(mktemp -d "$runtime/rollback/release.XXXXXXXX")"
  cp -p "$compose_env" "$rollback/compose.env"
  cp -p "$router_bundle" "$rollback/barbarossa-router.pex"
  previous_container="$(compose_with_env "$compose_env" ps --all --quiet hermes)"
  previous_files="$("$docker" inspect --format '{{ index .Config.Labels "com.docker.compose.project.config_files" }}' "$previous_container")"
  previous_compose="${previous_files%%,*}"
  [ -f "$previous_compose" ] || { printf 'previous Compose source is unavailable\n' >&2; exit 1; }
  # Resolved private snapshot retains the previous source mounts and settings.
  # The old release directory must remain present for those bind mounts.
  (
    unset BARBAROSSA_IMAGE_TAG BARBAROSSA_RUNTIME_DIR
    "$docker" compose --env-file "$(dirname "$previous_compose")/.env" \
      --env-file "$compose_env" -f "$previous_compose" config --format json
  ) > "$rollback/compose.json"
  [ -s "$rollback/compose.json" ] || { printf 'previous Compose snapshot is empty\n' >&2; exit 1; }
  printf 'services:\n' > "$rollback/images.yml"
  # Snapshot images actually used by the existing containers, including Hermes.
  # Local tags keep them available even if an upstream tag moves during pull.
  for service in forge recon hermes; do
    container="$(compose_with_env "$compose_env" ps --all --quiet "$service")"
    case "$container" in
      ''|*'
'*) printf 'cannot retain previous %s image: expected one container\n' "$service" >&2; exit 1 ;;
    esac
    previous_image="$("$docker" inspect --format '{{.Image}}' "$container")"
    [ -n "$previous_image" ] || { printf 'missing previous %s image\n' "$service" >&2; exit 1; }
    reference="barbarossa-rollback-$service:${rollback##*/}"
    "$docker" image tag "$previous_image" "$reference"
    printf '  %s:\n    image: %s\n    pull_policy: never\n' "$service" "$reference" >> "$rollback/images.yml"
  done
  printf 'staged\n' > "$rollback/status"
else
  ssh-keygen -q -t ed25519 -N "" -C "hermes@barbarossa" -f "$stage/worker_key"
  printf 'restrict,command="/usr/local/bin/worker-ssh-dispatch" %s\n' \
    "$(cat "$stage/worker_key.pub")" > "$stage/authorized_keys"
  chmod 0644 "$stage/authorized_keys"
fi

# From here, any failure restores the saved env/PEX and starts the prior images.
committed=1
if [ "$mode" = bootstrap ]; then
  mv "$stage/worker_key" "$worker_key"
  mv "$stage/worker_key.pub" "$worker_key.pub"
  mv "$stage/authorized_keys" "$authorized_keys"
  touch "$known_hosts"
fi
# Optional secret files are required as bind-mount sources. Existing credentials
# are never rewritten, chmodded, removed or included in deployment output.
for credential in github_token gmail_user; do
  [ -e "$runtime/$credential" ] || touch "$runtime/$credential"
done
mv -f "$stage/compose.env" "$compose_env"
mv -f "$stage/barbarossa-router.pex" "$router_bundle"

compose_with_env "$compose_env" \
  up -d --no-build --pull never --force-recreate --wait --wait-timeout 300 forge recon

# Assignment has to propagate exec failure; printf "$(...)" would hide it.
forge_host="$(compose_with_env "$compose_env" exec -T forge cat /ssh-host-keys/ssh_host_ed25519_key.pub)"
recon_host="$(compose_with_env "$compose_env" exec -T recon cat /ssh-host-keys/ssh_host_ed25519_key.pub)"
[ -n "$forge_host" ] && [ -n "$recon_host" ] || { printf 'missing worker host key\n' >&2; exit 1; }
printf 'forge %s\nrecon %s\n' "$forge_host" "$recon_host" > "$stage/known_hosts"
if [ "$mode" = update ]; then
  cmp -s "$stage/known_hosts" "$known_hosts" || {
    printf 'worker host keys changed unexpectedly; refusing to replace trust\n' >&2
    exit 1
  }
else
  chmod 0644 "$stage/known_hosts"
  mv -f "$stage/known_hosts" "$known_hosts"
fi

# --no-deps avoids an unnecessary second replacement of the healthy workers.
compose_with_env "$compose_env" \
  up -d --no-deps --no-build --pull never --force-recreate --wait --wait-timeout 300 hermes
BARBAROSSA_RUNTIME_DIR="$runtime" "$root/scripts/smoke-remote.sh"
complete=1
if [ -n "$rollback" ]; then
  printf 'deployed\n' > "$rollback/status"
  printf 'previous release retained: %s\n' "$rollback"
fi
