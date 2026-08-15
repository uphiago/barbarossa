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

# Specify CLI (spec-kit) — install on first boot (root, before dropping to forge).
# spec-kit enables spec-driven development for Codex jobs (/speckit.* skills).
# /home/forge is a writable named volume, so uv uses the default cache there.
if command -v uv >/dev/null 2>&1; then
  SPECIFY_TAG="${BARBAROSSA_SPECIFY_TAG:-v0.12.11}"
  uv tool install specify-cli \
    --from "git+https://github.com/github/spec-kit.git@${SPECIFY_TAG}" \
    >/dev/null 2>&1 || true
fi

auth_source="${CODEX_AUTH_SOURCE_FILE:-/run/secrets/codex_auth_json}"
auth_target="${CODEX_AUTH_JSON_FILE:-/home/forge/.codex/auth.json}"
if [ -s "$auth_source" ]; then
  python3 -c \
    'import json,sys; value=json.load(open(sys.argv[1], encoding="utf-8")); assert isinstance(value, dict) and ("tokens" in value or "OPENAI_API_KEY" in value)' \
    "$auth_source"
  install -o forge -g forge -m 0600 \
    "$auth_source" "$auth_target"
fi

github_token_file="${GH_TOKEN_FILE:-/run/barbarossa-secrets/github_token}"
codex_model="${BARBAROSSA_CODEX_MODEL:?BARBAROSSA_CODEX_MODEL is required}"
codex_reasoning="${BARBAROSSA_CODEX_REASONING_EFFORT:?BARBAROSSA_CODEX_REASONING_EFFORT is required}"
codex_subagents="${BARBAROSSA_CODEX_MAX_SUBAGENTS:?BARBAROSSA_CODEX_MAX_SUBAGENTS is required}"

for value in \
  "$auth_target" \
  "$github_token_file" \
  "$codex_model" \
  "$codex_reasoning" \
  "$codex_subagents"; do
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
BARBAROSSA_CODEX_MAX_SUBAGENTS=$codex_subagents"

exec /usr/local/bin/worker-entrypoint "$@" -o "$session_environment"
