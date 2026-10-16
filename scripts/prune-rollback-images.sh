#!/bin/sh
# Prune stale Barbarossa rollback releases (operator tool; not part of deploy).
#
# Every update retains one rollback release: a directory under
# $BARBAROSSA_RUNTIME_DIR/rollback plus barbarossa-rollback-* image tags of the
# release that was replaced. Older releases accumulate and can fill the host
# disk (see docs/2026-10-16-deploy-disk-incident.md). This tool keeps the
# newest rollback directory and removes older directories together with their
# image tags; a tag shared with the retained release is dropped as well, while
# its image survives through the retained tags. Running containers, the
# retained release's own tags, and non-barbarossa images are never touched.
#
# Dry-run by default; pass --apply to execute. Refuses to run while a
# deployment lock exists.
set -eu

runtime="${BARBAROSSA_RUNTIME_DIR:-$HOME/.config/barbarossa/runtime}"
docker="${DOCKER:-docker}"
rollback_root="$runtime/rollback"

apply=0
case "${1:-}" in
  "") apply=0 ;;
  --apply) apply=1 ;;
  *) printf 'usage: %s [--apply]\n' "$0" >&2; exit 2 ;;
esac
[ "$#" -le 1 ] || { printf 'usage: %s [--apply]\n' "$0" >&2; exit 2; }

if [ -e "$runtime/.deploy.lock" ]; then
  printf 'deployment lock present: %s; refusing to prune\n' "$runtime/.deploy.lock" >&2
  exit 1
fi
"$docker" info >/dev/null 2>&1 || {
  printf 'docker is unavailable; refusing to prune\n' >&2
  exit 1
}
[ -d "$rollback_root" ] || {
  printf 'nothing to prune: %s does not exist\n' "$rollback_root"
  exit 0
}

# Newest rollback directory (by mtime) is retained.
listed="$(ls -1dt "$rollback_root"/release.* 2>/dev/null || true)"
newest="$(printf '%s\n' "$listed" | head -n 1)"
stale="$(printf '%s\n' "$listed" | tail -n +2)"
[ -n "$newest" ] || { printf 'nothing to prune: no rollback releases\n'; exit 0; }

refs_of() {
  [ -f "$1/images.yml" ] || return 0
  awk '/^[[:space:]]+image:[[:space:]]/ { print $2 }' "$1/images.yml"
}

keep_ids=""
for ref in $(refs_of "$newest"); do
  id="$("$docker" image inspect --format '{{.Id}}' "$ref" 2>/dev/null || true)"
  [ -n "$id" ] && keep_ids="$keep_ids $id"
done

plan=""
for dir in $stale; do
  for ref in $(refs_of "$dir"); do
    id="$("$docker" image inspect --format '{{.Id}}' "$ref" 2>/dev/null || true)"
    [ -n "$id" ] || continue
    case " $keep_ids " in
      *" $id "*)
        # Image shared with the retained release: drop only the stale tag.
        plan="$plan $ref"
        ;;
      *)
        for tag in $("$docker" images --no-trunc --format '{{.ID}} {{.Repository}}:{{.Tag}}' |
          awk -v id="$id" '$1 == id { print $2 }'); do
          case "$tag" in
            barbarossa-rollback-*|ghcr.io/uphiago/barbarossa-*) plan="$plan $tag" ;;
          esac
        done
        ;;
    esac
  done
done

unique=""
for tag in $plan; do
  case " $unique " in *" $tag "*) ;; *) unique="$unique $tag" ;; esac
done

printf 'retained rollback release: %s\n' "$newest"
for dir in $stale; do
  printf 'stale rollback release:    %s\n' "$dir"
done
if [ -n "$unique" ]; then
  printf 'stale release tags to remove:%s\n' "$unique"
else
  printf 'no stale tags to remove\n'
fi

if [ "$apply" -eq 1 ] && [ -n "$unique" ]; then
  # Running containers keep their images even if a tag is removed; failures
  # here are reported by docker and leave the tag in place.
  "$docker" rmi $unique || true
fi

for dir in $stale; do
  remaining=""
  for ref in $(refs_of "$dir"); do
    if "$docker" image inspect "$ref" >/dev/null 2>&1; then
      remaining="$remaining $ref"
    fi
  done
  if [ -n "$remaining" ]; then
    printf 'kept %s (images still present:%s)\n' "$dir" "$remaining" >&2
    continue
  fi
  if [ "$apply" -eq 1 ]; then
    rm -rf -- "$dir"
    printf 'removed %s\n' "$dir"
  else
    printf 'would remove %s\n' "$dir"
  fi
done

[ "$apply" -eq 1 ] || printf 'dry-run; re-run with --apply to execute\n'
