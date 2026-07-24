#!/bin/bash
LOGFILE="/root/output/cmd.log"
log() {
    local ts clean
    ts=$(date '+%H:%M:%S')
    clean=$(echo "$1" | sed "s/'\"'\"'/'/g")
    echo "[$ts] $clean" >> "$LOGFILE"
}
if [[ -n "${SSH_ORIGINAL_COMMAND:-}" ]]; then
    log "${SSH_ORIGINAL_COMMAND}"
    exec bash -c "${SSH_ORIGINAL_COMMAND}"
fi
exec bash --login
