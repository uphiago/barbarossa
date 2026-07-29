#!/bin/bash
set -euo pipefail

root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
runtime="${BARBAROSSA_RUNTIME_DIR:-$HOME/.config/barbarossa/runtime}"

compose() {
  BARBAROSSA_RUNTIME_DIR="$runtime" "$root/scripts/compose.sh" "$@"
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

networks="$(compose ps -q | xargs "${DOCKER:-docker}" inspect \
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

evidence="$(mktemp -d)"
trap 'rm -rf "$evidence"' EXIT HUP INT TERM
chmod 0700 "$evidence"
compose config --format json > "$evidence/compose.json"
compose logs --since 15m --no-color hermes forge recon \
  > "$evidence/services.log"
chmod 0600 "$evidence/compose.json" "$evidence/services.log"
python3 - "$evidence/compose.json" "$evidence/services.log" "$runtime" <<'PY'
import json
import re
import sys
from pathlib import Path

config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
logs = Path(sys.argv[2]).read_text(encoding="utf-8", errors="replace")
runtime = Path(sys.argv[3])
secret_name = re.compile(
    r"(?:API_KEY|TOKEN|PASSWORD|SECRET)",
    re.IGNORECASE,
)
candidates: list[tuple[str, str]] = []

for service in config["services"].values():
    for name, value in service.get("environment", {}).items():
        if secret_name.search(name) and isinstance(value, str):
            candidates.append((name, value))

for name in ("codex_access_token", "github_token"):
    path = runtime / name
    if path.is_file():
        candidates.append((name, path.read_text(encoding="utf-8").strip()))

auth_path = runtime / "codex_auth.json"
if auth_path.is_file() and auth_path.stat().st_size:
    def strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for child in value.values():
                yield from strings(child)
        elif isinstance(value, list):
            for child in value:
                yield from strings(child)

    for value in strings(json.loads(auth_path.read_text(encoding="utf-8"))):
        candidates.append(("codex_auth", value))

for name, value in candidates:
    if len(value) >= 8 and value in logs:
        raise SystemExit(f"secret value from {name} found in container logs")

if "BEGIN OPENSSH PRIVATE KEY" in logs:
    raise SystemExit("private key marker found in container logs")
PY
rm -rf "$evidence"
trap - EXIT HUP INT TERM

printf 'barbarossa remote smoke checks passed\n'
