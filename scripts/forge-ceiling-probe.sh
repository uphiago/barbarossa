#!/bin/bash
# forge-ceiling-probe.sh — measures the real ceiling of the Forge container
# (cgroup memory/PIDs/OOM) with raw opencode + deepseek-free instances launched
# via docker exec, OUTSIDE the lane protocol (no flock; jobs are untouched).
#
# Run ON the deployment host as a user with docker access (reads the container
# cgroup directly). Escalation ladder 2 4 6 8 12 16; stops at the first wall:
# cgroup OOM kill, PIDs denial, provider rate limit, or container trouble.
# Artifacts: /tmp/tora-$TS on the host, /workspace/.tora/$TS inside the Forge.
# Context and measurements: docs/2026-10-16-opencode-free-tier-ops.md
# Usage: forge-ceiling-probe.sh [maxK]
set -u

MAXK="${1:-}"
CONT=barbarossa-forge-1
MODEL='opencode/deepseek-v4.1-flash-free#low'
PROMPT='Use the bash tool to run: sleep 120. Then reply exactly TORA_OK. Do not spawn subagents and do not do anything else.'
TS=$(date -u +%Y%m%dT%H%M%SZ)
OUT=/tmp/tora-$TS
BASE=/workspace/.tora/$TS
mkdir -p "$OUT"

if [ -n "$MAXK" ]; then
  LADDER=""
  for k in 2 4 6 8 12 16; do [ "$k" -le "$MAXK" ] && LADDER="$LADDER $k"; done
  [ -z "$LADDER" ] && LADDER=" $MAXK"
else
  LADDER=" 2 4 6 8 12 16"
fi

cid=$(docker inspect -f '{{.Id}}' "$CONT") || { echo "FATAL: container not found"; exit 1; }
CG=/sys/fs/cgroup/system.slice/docker-$cid.scope
[ -d "$CG" ] || { echo "FATAL: cgroup path missing: $CG"; exit 1; }

log() { echo "[tora] $*"; echo "[tora] $*" >> "$OUT/tora.log"; }

oom_count() { awk '/^oom_kill/{print $2}' "$CG/memory.events" 2>/dev/null || echo 0; }
pids_denials() { awk '/^max /{print $2}' "$CG/pids.events" 2>/dev/null || echo 0; }
forge_ok() { [ "$(docker inspect -f '{{.State.Running}}' "$CONT" 2>/dev/null)" = "true" ]; }

log "ts=$TS host=$(hostname) forge=$cid ladder:$(echo $LADDER | tr ' ' ',') model=$MODEL"
log "baseline: mem=$(( $(cat "$CG/memory.current") / 1048576 ))MiB pids=$(cat "$CG/pids.current") oom_kill=$(oom_count) pids_denials=$(pids_denials)"
log "artifacts: host=$OUT container=$BASE"

confirm_after=""
verdict=""

for K in $LADDER; do
  RD=$BASE/r$K
  SUM=$OUT/r$K.summary
  STATS=$OUT/r$K.stats.csv
  log "round K=$K start"

  docker exec -i -u forge -e RD="$RD" -e K="$K" "$CONT" sh -s <<'EOS'
i=1
while [ "$i" -le "$K" ]; do
  d="$RD/i-$i"
  mkdir -p "$d/config" "$d/data" "$d/state" "$d/cache" "$d/tmp" "$d/home"
  cp -r /usr/local/share/barbarossa/opencode "$d/config/opencode"
  i=$((i+1))
done
EOS

  oom_before=$(oom_count)
  pev_before=$(pids_denials)
  spawn_fail=0
  errlog=$OUT/r$K.spawn.err
  : > "$errlog"

  i=1
  while [ "$i" -le "$K" ]; do
    d="$RD/i-$i"
    if ! docker exec -d -u forge \
      -e HOME="$d/home" -e TMPDIR="$d/tmp" -e LANG=C.UTF-8 -e TZ=UTC \
      -e XDG_CONFIG_HOME="$d/config" -e XDG_DATA_HOME="$d/data" \
      -e XDG_STATE_HOME="$d/state" -e XDG_CACHE_HOME="$d/cache" \
      -e TORA_MODEL="$MODEL" -e TORA_PROMPT="$PROMPT" \
      -w "$d" "$CONT" sh -c '
        date +%s > start
        timeout 600 /usr/local/bin/opencode run --standalone --auto --agent orchestrator \
          --model "$TORA_MODEL" "$TORA_PROMPT" >out.log 2>&1
        echo $? > exit
        date +%s > end
      ' 2>>"$errlog"; then
      spawn_fail=$((spawn_fail + 1))
    fi
    i=$((i + 1))
  done
  start_epoch=$(date +%s)
  log "round K=$K spawned (spawn_fail=$spawn_fail)"

  sleep 3
  consec0=0
  peak_mem=0; peak_anon=0; peak_pids=0; peak_alive=0; host_low=99999999
  while :; do
    mem=$(cat "$CG/memory.current" 2>/dev/null || echo 0)
    anon=$(awk '/^anon /{print $2; exit}' "$CG/memory.stat" 2>/dev/null)
    case "$anon" in ''|*[!0-9]*) anon=0 ;; esac
    pids=$(cat "$CG/pids.current" 2>/dev/null || echo 0)
    alive=$(docker top "$CONT" -eo pid,args 2>/dev/null | grep -E -c '[0-9]+ +timeout 600 /usr/local/bin/opencode run')
    hostavail=$(awk '/^MemAvailable/{print $2}' /proc/meminfo)
    [ "$mem" -gt "$peak_mem" ] && peak_mem=$mem
    [ "$anon" -gt "$peak_anon" ] && peak_anon=$anon
    [ "$pids" -gt "$peak_pids" ] && peak_pids=$pids
    [ "$alive" -gt "$peak_alive" ] && peak_alive=$alive
    [ "$hostavail" -lt "$host_low" ] && host_low=$hostavail
    echo "$(date -u +%s) alive=$alive mem=$mem anon=$anon pids=$pids hostavail_kb=$hostavail" >> "$STATS"
    if [ "$alive" -eq 0 ]; then
      consec0=$((consec0 + 1))
      [ "$consec0" -ge 2 ] && break
    else
      consec0=0
    fi
    now=$(date +%s)
    [ $((now - start_epoch)) -gt 900 ] && { log "round K=$K wall reached, alive=$alive"; break; }
    sleep 5
  done
  elapsed=$(( $(date +%s) - start_epoch ))

  docker exec -i -u forge -e RD="$RD" -e K="$K" "$CONT" sh -s > "$SUM" <<'EOS'
i=1
while [ "$i" -le "$K" ]; do
  d="$RD/i-$i"
  code=$(cat "$d/exit" 2>/dev/null || echo NA)
  cls=other
  if [ "$code" = "0" ] && grep -q TORA_OK "$d/out.log" 2>/dev/null; then
    cls=pass
  elif grep -q 'Rate limit exceeded' "$d/out.log" 2>/dev/null; then
    cls=rate_limit
  fi
  last=$(tail -1 "$d/out.log" 2>/dev/null | tr -d '\r' | head -c 140)
  s=$(cat "$d/start" 2>/dev/null || echo ?)
  e=$(cat "$d/end" 2>/dev/null || echo ?)
  if [ "$s" != "?" ] && [ "$e" != "?" ]; then dur=$((e - s))s; else dur=?; fi
  printf 'i-%s exit=%s class=%s dur=%s last=%s\n' "$i" "$code" "$cls" "$dur" "$last"
  i=$((i + 1))
done
EOS

  pass=$(grep -c 'class=pass' "$SUM" || true)
  rl=$(grep -c 'class=rate_limit' "$SUM" || true)
  other=$(grep -c 'class=other' "$SUM" || true)
  oom_delta=$(( $(oom_count) - oom_before ))
  pids_denied=$(( $(pids_denials) - pev_before ))
  st=$(docker inspect -f '{{.State.Running}}/{{.State.Health.Status}}/{{.State.OOMKilled}}/{{.RestartCount}}' "$CONT" 2>/dev/null || echo DOWN)
  log "round K=$K done wall=${elapsed}s alive_peak=$peak_alive pass=$pass rl=$rl other=$other oom_kills=+$oom_delta pids_denied=+$pids_denied spawn_fail=$spawn_fail mem_peak=$(( peak_mem / 1048576 ))MiB anon_peak=$(( peak_anon / 1048576 ))MiB pids_peak=$peak_pids host_min_avail=$(( host_low / 1024 ))MiB forge=$st"

  if ! forge_ok; then verdict="forge container died/stopped at K=$K"; log "$verdict"; break; fi

  if [ "$oom_delta" -gt 0 ] || [ "$pids_denied" -gt 0 ] || [ "$spawn_fail" -gt 0 ]; then
    if [ "$confirm_after" = "1" ]; then
      verdict="machine wall latched at K=$K (oom/pids-denied/spawn-fail again)"; log "$verdict"; break
    fi
    confirm_after=1
    log "machine-wall evidence at K=$K -> one confirm round"
  elif [ "$confirm_after" = "1" ]; then
    verdict="machine wall just below (K=$K clean, evidence was previous round)"; log "$verdict"; break
  fi

  if [ "$pass" -eq 0 ] && [ "$rl" -ge $(( (K * 3 + 3) / 4 )) ]; then
    verdict="provider wall: no session served at K=$K (rl=$rl/$K)"; log "$verdict"; break
  fi

  sleep 5
done

log "cgroup lifetime peaks: mem=$(( $(cat "$CG/memory.peak") / 1048576 ))MiB pids=$(cat "$CG/pids.peak")"
log "verdict: ${verdict:-ladder completed ($LADDER)}"
cp "$OUT/tora.log" "$OUT/FINAL.txt"
log "artifacts: $OUT (host) | $BASE (container)"
ls -la "$OUT"
