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
for secret in codex_access_token github_token; do
  source="/run/secrets/$secret"
  if [ -s "$source" ]; then
    install -o forge -g forge -m 0600 \
      "$source" "/run/barbarossa-secrets/$secret"
  fi
done

auth_source="${CODEX_AUTH_SOURCE_FILE:-/run/secrets/codex_auth_json}"
auth_target="${CODEX_AUTH_JSON_FILE:-/home/forge/.codex/auth.json}"
if [ -s "$auth_source" ]; then
  python3 -c \
    'import json,sys; value=json.load(open(sys.argv[1], encoding="utf-8")); assert isinstance(value, dict) and ("tokens" in value or "OPENAI_API_KEY" in value)' \
    "$auth_source"
  install -o forge -g forge -m 0600 \
    "$auth_source" "$auth_target"
fi

exec /usr/local/bin/worker-entrypoint "$@"
