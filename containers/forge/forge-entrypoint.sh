#!/bin/sh
set -eu

install -d -o forge -g forge -m 0700 \
  /home/forge/.codex \
  /home/forge/.codex/skills \
  /home/forge/.codex/skills/barbarossa-artifacts
install -o forge -g forge -m 0600 \
  /usr/local/share/barbarossa/codex/config.toml \
  /home/forge/.codex/config.toml
install -o forge -g forge -m 0600 \
  /usr/local/share/barbarossa/codex/SKILL.md \
  /home/forge/.codex/skills/barbarossa-artifacts/SKILL.md

install -d -o forge -g forge -m 0700 /run/barbarossa-secrets
for secret in github_token gmail_user gmail_app_password; do
  source="/run/secrets/$secret"
  if [ -s "$source" ]; then
    install -o forge -g forge -m 0600 \
      "$source" "/run/barbarossa-secrets/$secret"
  fi
done

auth_source="${CODEX_AUTH_SOURCE_FILE:-/run/secrets/codex_auth_json}"
auth_target="${CODEX_AUTH_JSON_FILE:-/home/forge/.codex/auth.json}"
# ChatGPT refresh tokens rotate server-side on use: the working copy inside
# this container drifts ahead of the deployed credential. Install the source
# only to bootstrap the volume, or when it is newer than the copy in place;
# a used-up refresh token must never clobber a rotated copy.
refresh_is_newer() (
  python3 - "$auth_source" "$auth_target" <<'PY'
import json
import pathlib
import sys


def stamp(path: pathlib.Path) -> str:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if not isinstance(value, dict):
        return ""
    return str(value.get("last_refresh", ""))


source, target = (pathlib.Path(value) for value in sys.argv[1:3])
if not target.exists():
    raise SystemExit(0)
source_stamp = stamp(source)
raise SystemExit(0 if source_stamp and source_stamp > stamp(target) else 1)
PY
)
if [ -s "$auth_source" ]; then
  python3 -c \
    'import json,sys; value=json.load(open(sys.argv[1], encoding="utf-8")); assert isinstance(value, dict) and ("tokens" in value or "OPENAI_API_KEY" in value)' \
    "$auth_source"
  if refresh_is_newer; then
    install -o forge -g forge -m 0600 \
      "$auth_source" "$auth_target"
  fi
fi

github_token_file="${GH_TOKEN_FILE:-/run/barbarossa-secrets/github_token}"
codex_model="${BARBAROSSA_CODEX_MODEL:?BARBAROSSA_CODEX_MODEL is required}"
codex_reasoning="${BARBAROSSA_CODEX_REASONING_EFFORT:?BARBAROSSA_CODEX_REASONING_EFFORT is required}"
codex_subagents="${BARBAROSSA_CODEX_MAX_SUBAGENTS:?BARBAROSSA_CODEX_MAX_SUBAGENTS is required}"
opencode_model="${BARBAROSSA_OPENCODE_MODEL:?BARBAROSSA_OPENCODE_MODEL is required}"
opencode_variant="${BARBAROSSA_OPENCODE_VARIANT:?BARBAROSSA_OPENCODE_VARIANT is required}"

for value in \
  "$auth_target" \
  "$github_token_file" \
  "$codex_model" \
  "$codex_reasoning" \
  "$codex_subagents" \
  "$opencode_model" \
  "$opencode_variant"; do
  case "$value" in
    "" | *[!A-Za-z0-9._:/+-]*)
      printf 'invalid Forge session setting\n' >&2
      exit 1
      ;;
  esac
done

session_environment="SetEnv=\
CODEX_AUTH_JSON_FILE=$auth_target \
GH_TOKEN_FILE=$github_token_file \
BARBAROSSA_CODEX_MODEL=$codex_model \
BARBAROSSA_CODEX_REASONING_EFFORT=$codex_reasoning \
BARBAROSSA_CODEX_MAX_SUBAGENTS=$codex_subagents \
BARBAROSSA_OPENCODE_MODEL=$opencode_model \
BARBAROSSA_OPENCODE_VARIANT=$opencode_variant"

exec /usr/local/bin/worker-entrypoint "$@" -o "$session_environment"
