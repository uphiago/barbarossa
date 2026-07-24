#!/bin/bash
set -euo pipefail

echo "╔══════════════════════════════════════╗"
echo "║        barbarossa setup              ║"
echo "╚══════════════════════════════════════╝"

cd "$(dirname "$0")"

# ─── 1. Validate .env ───
[ ! -f .env ] && { echo "Missing .env. Copy .env.example and fill in your keys."; exit 1; }
set -a; source .env; set +a

missing=""
[[ -z "${HERMES_PROVIDER:-}" ]] && missing="$missing HERMES_PROVIDER"
[[ -z "${HERMES_MODEL:-}" ]] && missing="$missing HERMES_MODEL"
[[ -z "${TELEGRAM_BOT_TOKEN:-}" ]] && missing="$missing TELEGRAM_BOT_TOKEN"
[[ -z "${DEEPSEEK_API_KEY:-}" ]] && [[ -z "${OPENROUTER_API_KEY:-}" ]] && missing="$missing API_KEY"

if [[ -n "$missing" ]]; then
  echo "Missing env vars:$missing"
  echo "Check .env.example for required fields."
  exit 1
fi

# ─── 2. SSH key ───
if grep -q "^BARBAROSSA_SSH_KEY=" .env 2>/dev/null; then
    KEY_PATH="$(grep "^BARBAROSSA_SSH_KEY=" .env | cut -d= -f2-)"
else
    KEY_PATH="$HOME/.ssh/barbarossa_key"
    echo "BARBAROSSA_SSH_KEY=$KEY_PATH" >> .env
fi

if [ ! -f "$KEY_PATH" ]; then
    echo "[+] Generating SSH key..."
    ssh-keygen -t ed25519 -f "$KEY_PATH" -N "" -C "barbarossa" >/dev/null 2>&1
fi

# ─── 3. SSH authorized_keys ───
mkdir -p worker/ssh-keys
cp "$KEY_PATH.pub" worker/ssh-keys/authorized_keys

# ─── 4. Build & start ───
RUNNING=$(docker ps --filter name=hermes -q 2>/dev/null | wc -l)
if [ "$RUNNING" -gt 0 ]; then
    echo "[!] Cluster already running. Use 'docker compose restart' or 'docker compose down && ./setup.sh'"
    exit 1
fi

echo "[+] Building & starting cluster..."
docker compose up -d --build
sleep 5

# ─── 5. Inject SSH key into hermes ───
docker exec hermes mkdir -p /opt/data/ssh
if ! docker exec hermes test -f /opt/data/ssh/key 2>/dev/null; then
    docker cp "$KEY_PATH" hermes:/opt/data/ssh/key
    docker exec hermes chmod 600 /opt/data/ssh/key
    docker exec hermes chown hermes:hermes /opt/data/ssh/key
    echo "    + SSH key injected"
fi

# ─── 6. Copy key to charlie (inter-worker SSH) ───
if ! docker exec charlie test -f /root/.ssh/id_ed25519 2>/dev/null; then
    docker cp "$KEY_PATH" charlie:/root/.ssh/id_ed25519
    docker exec charlie chmod 600 /root/.ssh/id_ed25519
    echo "    + SSH key copied to charlie"
fi

# ─── 7. Hermes config ───
echo "[+] Configuring Hermes..."

docker exec hermes hermes config set terminal.backend ssh
docker exec hermes hermes config set model.provider "$HERMES_PROVIDER"
docker exec hermes hermes config set model.name "$HERMES_MODEL"
docker exec hermes hermes config set model.default "$HERMES_MODEL"
docker exec hermes hermes config set delegation.provider "$HERMES_PROVIDER"
docker exec hermes hermes config set delegation.model "$HERMES_MODEL"

# Auxiliary models
for aux in title_generation; do
    docker exec hermes hermes config set "auxiliary.${aux}.provider" "$HERMES_PROVIDER" 2>/dev/null || true
    docker exec hermes hermes config set "auxiliary.${aux}.model" "$HERMES_MODEL" 2>/dev/null || true
done

# Limits
docker exec hermes hermes config set tool_output.max_bytes 200000
docker exec hermes hermes config set tool_output.max_lines 5000
docker exec hermes hermes config set agent.max_turns 120
docker exec hermes hermes config set agent.disabled_toolsets vision

# ─── 8. Inject AGENTS.md + SOUL.md ───
if [ -f AGENTS.md ]; then
    docker cp AGENTS.md hermes:/opt/data/AGENTS.md
    docker exec hermes chown hermes:hermes /opt/data/AGENTS.md
    echo "    + AGENTS.md"
fi
if [ -f SOUL.md ]; then
    docker cp SOUL.md hermes:/opt/data/SOUL.md
    docker exec hermes chown hermes:hermes /opt/data/SOUL.md
    echo "    + SOUL.md"
fi

# ─── 9. Health check ───
echo "[+] Testing SSH hermes→charlie..."
attempt=0
while [ $attempt -lt 10 ]; do
    if docker exec hermes su -s /bin/sh hermes -c \
        "ssh -i /opt/data/ssh/key -o StrictHostKeyChecking=no -o ConnectTimeout=3 root@charlie 'echo OK'" 2>&1 | grep -q "^OK"; then
        echo "    ✅ SSH pipe healthy"
        break
    fi
    attempt=$((attempt + 1))
    sleep 2
done

# ─── 10. Provider test ───
echo "[+] Testing model..."
if timeout 30 docker exec hermes hermes chat -q "reply with only: OK" > /tmp/barbarossa-test.txt 2>/dev/null; then
    if grep -q OK /tmp/barbarossa-test.txt 2>/dev/null; then
        echo "    ✅ Provider $HERMES_PROVIDER working"
    else
        echo "    ⚠️  Provider returned unexpected response:"
        head -3 /tmp/barbarossa-test.txt | sed 's/^/    /'
    fi
else
    echo "    ⚠️  Provider test timed out. Check API key."
    echo "    Run: docker logs hermes --tail 30"
fi
rm -f /tmp/barbarossa-test.txt

echo ""
echo "╔══════════════════════════════════════╗"
echo "║   barbarossa ready                   ║"
echo "╚══════════════════════════════════════╝"
docker exec hermes hermes gateway status 2>/dev/null || true
