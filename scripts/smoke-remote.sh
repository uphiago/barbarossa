#!/bin/bash
set -euo pipefail

root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
runtime="${BARBAROSSA_RUNTIME_DIR:-$HOME/.config/barbarossa/runtime}"
docker="${DOCKER:-docker}"

compose() {
  if [ -f "$runtime/compose.env" ]; then
    "$docker" compose \
      --env-file "$root/.env" \
      --env-file "$runtime/compose.env" \
      -f "$root/docker-compose.yml" "$@"
  else
    "$docker" compose \
      --env-file "$root/.env" \
      -f "$root/docker-compose.yml" "$@"
  fi
}

diff -u \
  <(printf 'forge\nhermes\nrecon\n') \
  <(compose ps --status running --services | sort)

router() {
  compose exec -T --user hermes hermes /opt/hermes/.venv/bin/python \
    /opt/barbarossa-router/barbarossa-router.pex "$@"
}

job_id() {
  python3 -c 'import json,sys; print(json.load(sys.stdin)["job_id"])'
}

submit_and_assert_log() {
  local capability="$1"
  local expected_log="$2"
  shift 2
  local submitted id logs
  submitted="$(router submit --capability "$capability" "$@" --wait)"
  id="$(printf '%s' "$submitted" | job_id)"
  logs="$(router logs "$id")"
  python3 -c \
    'import json,sys; assert sys.argv[1] in json.load(sys.stdin)["stdout"]' \
    "$expected_log" <<<"$logs"
  printf 'verified %s\n' "$capability"
}

submit_and_assert_artifact() {
  local capability="$1"
  local expected_content="$2"
  shift 2
  local submitted id artifact
  submitted="$(router submit --capability "$capability" "$@" --wait)"
  id="$(printf '%s' "$submitted" | job_id)"
  artifact="$(router result "$id" | python3 -c \
    'import json,sys; print(next(path for path in json.load(sys.stdin)["artifacts"] if path.endswith("/outputs/body.bin")))')"
  compose exec -T --user hermes hermes \
    grep -Fq "$expected_content" "$artifact"
}

router health | python3 -c \
  'import json,sys; assert json.load(sys.stdin)["status"] == "ok"'
compose exec -T --user hermes hermes \
  /opt/hermes/.venv/bin/hermes mcp test barbarossa

submit_and_assert_log runtime.execute BARBAROSSA_RUNTIME_OK \
  --command 'printf BARBAROSSA_RUNTIME_OK'

submit_and_assert_log code.delegate BARBAROSSA_CODEX_OK \
  --prompt 'Reply with exactly BARBAROSSA_CODEX_OK.'
submit_and_assert_log code.delegate BARBAROSSA_SUBAGENT_OK \
  --prompt 'Spawn exactly one subagent to return BARBAROSSA_SUBAGENT_OK, then reply with that exact text.'

fixture="/opt/data/barbarossa-transfer/smoke.png"
compose exec -T --user hermes hermes sh -c \
  'install -d -m 0700 /opt/data/barbarossa-transfer &&
   printf "%s" "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=" |
   base64 -d > /opt/data/barbarossa-transfer/smoke.png'
submit_and_assert_log media.image.inspect BARBAROSSA_IMAGE_OK \
  --input-path "$fixture" \
  --prompt 'Inspect this image, then reply with exactly BARBAROSSA_IMAGE_OK.'

generated="$(router submit --capability media.image.generate \
  --prompt 'Generate a simple red square icon, then copy the generated PNG unchanged to outputs/red.png. Do not resize it or use ImageMagick or Pillow.' \
  --wait)"
generated_id="$(printf '%s' "$generated" | job_id)"
router result "$generated_id" | python3 -c \
  'import json,sys; data=json.load(sys.stdin); assert any(path.endswith((".png",".webp",".jpg",".jpeg")) for path in data["artifacts"])'

submit_and_assert_artifact network.fetch '"IsTor":false' \
  --url 'https://check.torproject.org/api/ip'
submit_and_assert_log network.tor '"IsTor":true' \
  --command 'curl -fsS --max-time 60 --retry 3 --retry-all-errors --retry-delay 2 https://check.torproject.org/api/ip'

compose exec -T --user forge forge id -u | grep -Fx 10001
compose exec -T --user recon recon id -u | grep -Fx 10002
for service in forge recon; do
  compose exec -T "$service" test ! -S /var/run/docker.sock
done

networks="$(compose ps -q | xargs "$docker" inspect \
  --format '{{.Name}} {{range $name, $_ := .NetworkSettings.Networks}}{{$name}} {{end}}')"
printf '%s\n' "$networks" | grep -F 'forge'
printf '%s\n' "$networks" | grep -F 'recon'
if printf '%s\n' "$networks" | awk \
  '/barbarossa-forge-1/{forge=$0}
   /barbarossa-recon-1/{recon=$0}
   END{exit(index(forge,"hermes-recon") || index(recon,"hermes-forge") ? 0 : 1)}'; then
  printf 'worker joined the wrong isolated network\n' >&2
  exit 1
fi

logs="$(compose logs --since 15m --no-color hermes forge recon)"
if printf '%s' "$logs" | grep -E \
  'CODEX_ACCESS_TOKEN|DEEPSEEK_API_KEY|BEGIN OPENSSH PRIVATE KEY'; then
  printf 'secret marker found in container logs\n' >&2
  exit 1
fi

printf 'barbarossa remote smoke checks passed\n'
