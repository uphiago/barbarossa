#!/usr/bin/env bash
set -euo pipefail

# vm — CLI wrapper to interact with the agentiko worker
# Usage: vm <command> [args]

SSH_HOST="${VM_HOST:-agentiko-worker}"
SSH_PORT="${VM_PORT:-2222}"
SSH_USER="${VM_USER:-root}"
SSH_KEY="${VM_KEY:-$HOME/.ssh/agentiko_key}"
TMUX_SESSION="agentiko"
SSH_ARGS="-o StrictHostKeyChecking=no"
[[ -n "$SSH_KEY" && -f "$SSH_KEY" ]] && SSH_ARGS="$SSH_ARGS -i $SSH_KEY"

main() {
    local cmd="${1:-help}"
    shift 2>/dev/null || true

    case "$cmd" in
        exec)   cmd_exec "$@" ;;
        run)    cmd_run "$@" ;;
        ps)     cmd_ps ;;
        attach) cmd_attach "$@" ;;
        logs)   cmd_logs "$@" ;;
        stop)   cmd_stop "$@" ;;
        get)    cmd_get "$@" ;;
        put)    cmd_put "$@" ;;
        tunnel) cmd_tunnel "$@" ;;
        shell)  cmd_shell ;;
        check)  cmd_check ;;
        *)      usage ;;
    esac
}

ssh_cmd()   { ssh $SSH_ARGS -p "$SSH_PORT" "$SSH_USER@$SSH_HOST" "$@"; }
scp_get()   { scp $SSH_ARGS -P "$SSH_PORT" "$SSH_USER@$SSH_HOST:$1" "${2:-.}"; }
scp_put()   { scp $SSH_ARGS -P "$SSH_PORT" "$1" "$SSH_USER@$SSH_HOST:${2:-/root/output/}"; }

usage() {
    cat >&2 <<'EOF'
Usage: vm <command> [args]

Commands:
  exec <cmd...>       Execute command, return output (sync)
  run <cmd...>        Execute in background via tmux (async)
  ps                  List running tasks
  attach [id]         Attach to running task (ctrl+b d to detach)
  logs <id>           Fetch task output
  stop <id>           Stop a task
  get <remote> [local]   Copy file from worker
  put <local> [remote]   Copy file to worker
  tunnel [port]       Open SOCKS proxy (default: 9050)
  shell               Interactive SSH
  check               Test connection and list available tools
EOF
}

cmd_exec() {
    ssh_cmd "cd /root/output && $*"
}

cmd_run() {
    local id
    id=$(shuf -i 10000000-99999999 -n 1 2>/dev/null || (date +%s | cksum | cut -d' ' -f1))
    ssh_cmd "tmux new-session -d -s $TMUX_SESSION -n $id 'cd /root/output && $*; exec bash'" >/dev/null 2>&1
    echo "task-$id"
}

cmd_ps() {
    ssh_cmd "tmux list-windows -t $TMUX_SESSION -F '#{window_name}' 2>/dev/null || echo 'No running tasks'"
}

cmd_attach() {
    local target="${1:-}"
    if [[ -z "$target" ]]; then
        ssh_cmd -t "tmux attach-session -t $TMUX_SESSION 2>/dev/null || echo 'No session'"
    else
        ssh_cmd -t "tmux select-window -t $TMUX_SESSION:$target 2>/dev/null; tmux attach-session -t $TMUX_SESSION 2>/dev/null || echo 'Task $target not found'"
    fi
}

cmd_logs() {
    local id="${1:-}"
    if [[ -z "$id" ]]; then
        echo "Usage: vm logs <task-id>" >&2
        exit 1
    fi
    ssh_cmd "tmux capture-pane -t $TMUX_SESSION:$id -p -S -1000 2>/dev/null || echo 'Task $id not found'"
}

cmd_stop() {
    local id="${1:-}"
    if [[ -z "$id" ]]; then
        echo "Usage: vm stop <task-id>" >&2
        exit 1
    fi
    ssh_cmd "tmux kill-window -t $TMUX_SESSION:$id 2>/dev/null || echo 'Task $id not found'"
}

cmd_get() {
    local remote="${1:-}"
    local dest="${2:-.}"
    if [[ -z "$remote" ]]; then
        echo "Usage: vm get <remote> [local]" >&2
        exit 1
    fi
    scp_get "$remote" "$dest"
}

cmd_put() {
    local src="${1:-}"
    local dest="${2:-/root/output/}"
    if [[ -z "$src" ]]; then
        echo "Usage: vm put <local> [remote]" >&2
        exit 1
    fi
    scp_put "$src" "$dest"
}

cmd_tunnel() {
    local port="${1:-9050}"
    echo "SOCKS proxy on localhost:$port (Ctrl+C to stop)" >&2
    ssh $SSH_ARGS -D "$port" -q -C -N "$SSH_USER@$SSH_HOST" -p "$SSH_PORT"
}

cmd_shell() {
    ssh_cmd
}

cmd_check() {
    echo "[*] Testing connection..."
    ssh_cmd "echo 'OK: connection working'"
    echo ""
    echo "[*] Available tools:"
    # shellcheck disable=SC2016
    ssh_cmd 'for cmd in subfinder httpx dnsx nuclei ffuf nmap masscan dig curl python3; do which $cmd >/dev/null 2>&1 && echo "  [OK] $cmd" || echo "  [--] $cmd (missing)"; done'
    echo ""
    echo "[*] Uptime:"
    ssh_cmd "uptime"
}

main "$@"
