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

exec /usr/local/bin/worker-entrypoint "$@"
