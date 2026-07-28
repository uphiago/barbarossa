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

auth_source="${CODEX_AUTH_JSON_FILE:-/run/secrets/codex_auth_json}"
if [ -s "$auth_source" ]; then
  python3 -c \
    'import json,sys; value=json.load(open(sys.argv[1], encoding="utf-8")); assert isinstance(value, dict) and ("tokens" in value or "OPENAI_API_KEY" in value)' \
    "$auth_source"
  install -o forge -g forge -m 0600 \
    "$auth_source" /home/forge/.codex/auth.json
fi

exec /usr/local/bin/worker-entrypoint "$@"
