#!/bin/sh
set -eu

case "${SSH_ORIGINAL_COMMAND:-}" in
  "barbarossa-worker rpc")
    exec /usr/local/bin/barbarossa-worker rpc
    ;;
  barbarossa-worker\ upload\ job_*)
    exec /usr/local/bin/barbarossa-worker upload \
      "${SSH_ORIGINAL_COMMAND##* }"
    ;;
  barbarossa-worker\ download\ job_*)
    exec /usr/local/bin/barbarossa-worker download \
      "${SSH_ORIGINAL_COMMAND##* }"
    ;;
  *)
    printf 'command denied\n' >&2
    exit 126
    ;;
esac
