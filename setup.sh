#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

LOGFILE="$SCRIPT_DIR/setup.log"
exec > >(tee -a "$LOGFILE") 2>&1

echo "╔════════════════════════════════════════╗"
echo "║        barbarossa setup                  ║"
echo "╚════════════════════════════════════════╝"
echo ""

# ─── 0. Prerequisites ───
if ! command -v docker >/dev/null 2>&1; then
    echo "[!] Docker not found."
    exit 1
fi

# ─── 1. .env ───
if [ ! -f .env ]; then
    echo "[!] .env not found."
    echo "    cp .env.example .env && nano .env"
    exit 1
fi
source .env

# ─── 2. Validate required vars ───
missing=""
[[ -z "${WORKER_HOST:-}" ]] && missing="$missing WORKER_HOST"
[[ -z "${WORKER_PORT:-}" ]] && missing="$missing WORKER_PORT"
[[ -z "${WORKER_USER:-}" ]] && missing="$missing WORKER_USER"
[[ -z "${HERMES_PROVIDER:-}" ]] && missing="$missing HERMES_PROVIDER"
[[ -z "${HERMES_MODEL:-}" ]] && missing="$missing HERMES_MODEL"
if [[ -n "$missing" ]]; then
    echo "[!] Missing required vars in .env:$missing"
    exit 1
fi

# ─── 3. SSH key ───
if grep -q "^BARBAROSSA_SSH_KEY=" .env 2>/dev/null; then
    KEY_PATH="$(grep "^BARBAROSSA_SSH_KEY=" .env | cut -d= -f2-)"
    KEY_PATH="${KEY_PATH/#\~/$HOME}"
else
    KEY_PATH="$HOME/.ssh/key"
    echo "BARBAROSSA_SSH_KEY=$KEY_PATH" >> .env
fi

if [ ! -f "$KEY_PATH" ]; then
    echo "[+] Generating SSH key: $KEY_PATH"
    mkdir -p "$(dirname "$KEY_PATH")"
    ssh-keygen -t ed25519 -f "$KEY_PATH" -N "" -C "barbarossa" >/dev/null 2>&1
else
    echo "[+] Using existing SSH key: $KEY_PATH"
fi

# ─── 4. Worker authorized_keys ───
mkdir -p charlie/ssh-keys
cp "${KEY_PATH}.pub" charlie/ssh-keys/authorized_keys
chmod 600 charlie/ssh-keys/authorized_keys
echo "[+] Worker authorized_keys ready"

# ─── 5. Handle running containers ───
RUNNING=$(docker ps --filter name=hermes -q 2>/dev/null | wc -l)
if [ "$RUNNING" -gt 0 ]; then
    echo "[+] Stopping existing containers..."
    docker compose down 2>/dev/null || true
fi

# ─── 6. Build ───
echo ""
echo "══════════════ Building ══════════════"
docker compose build
echo "══════════════ Build done ══════════════"

# ─── 7. Start ───
echo ""
echo "══════════════ Starting ══════════════"
docker compose up -d
echo "══════════════ Containers up ══════════════"

# ─── 8. Wait for Hermes ───
echo "[+] Waiting for Hermes to be ready..."
for i in $(seq 1 20); do
    if docker exec hermes true 2>/dev/null; then
        echo "[+] Hermes is up (${i}s)"
        break
    fi
    sleep 1
done

# ─── 9. Inject SSH key + config into Hermes ───
echo "[+] Setting up SSH..."
docker exec hermes mkdir -p /opt/data/.ssh
if ! docker exec hermes test -f /opt/data/ssh/key 2>/dev/null; then
    docker exec hermes mkdir -p /opt/data/ssh
    docker cp "$KEY_PATH" hermes:/opt/data/ssh/key
fi
docker exec -i hermes sh -c 'cat > /opt/data/.ssh/config && chown -R hermes:hermes /opt/data/.ssh && chmod 600 /opt/data/ssh/key' << 'SSHEOF'
Host charlie
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
SSHEOF

# ─── 10b. Inject AGENTS.md + SOUL.md ───
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

# ─── 11. Configure Hermes ───
echo "[+] Configuring model: $HERMES_PROVIDER / $HERMES_MODEL"
docker exec hermes hermes config set model.provider "$HERMES_PROVIDER"
docker exec hermes hermes config set model.name "$HERMES_MODEL"
docker exec hermes hermes config set model.default "$HERMES_MODEL"
docker exec hermes hermes config set terminal.ssh.key /opt/data/ssh/key
docker exec hermes hermes config set agent.environment_hint "Worker container (SSH from Hermes). Hermes home mounted at /hermes/ (read/write via terminal). NEVER use write_file or patch on /hermes/ or /root/.hermes/ — always use terminal: cat > /hermes/path << 'EOF'. After writing: chown -R hermes:hermes /hermes/. Existing skills at /hermes/skills/ (recon/, meta/, chains/, auth/, infra/). AGENTS.md at /hermes/AGENTS.md. Recon reports at /root/output/recon_us/. Tools: nmap, masscan, subfinder, httpx, dnsx, nuclei, ffuf, amass, naabu, katana, dig, curl, python3."

echo "[+] Tuning limits for 1M context..."
docker exec hermes hermes config set tool_output.max_bytes 200000
docker exec hermes hermes config set tool_output.max_lines 5000
docker exec hermes hermes config set file_read_max_chars 200000
docker exec hermes hermes config set context_file_max_chars 30000

echo "[+] Hardening gateway..."
docker exec hermes hermes config set tool_loop_guardrails.hard_stop_enabled true
docker exec hermes hermes config set agent.max_turns 120
docker exec hermes hermes config set max_concurrent_sessions 10
docker exec hermes hermes config set agent.disabled_toolsets vision

echo "[+] Setting cheaper models for delegation and auxiliary..."
docker exec hermes hermes config set delegation.provider "$HERMES_PROVIDER"
docker exec hermes hermes config set delegation.model "$HERMES_MODEL"

for aux in background_review compression vision web_extract title_generation skills_hub triage_specifier kanban_decomposer profile_describer curator monitor; do
    docker exec hermes hermes config set "auxiliary.${aux}.provider" "$HERMES_PROVIDER"
    docker exec hermes hermes config set "auxiliary.${aux}.model" "$HERMES_MODEL"
done

# ─── 12. Health check: SSH Hermes → Worker ───
echo "[+] Health check: SSH Hermes → Worker..."
HEALTH_OK=false
for attempt in $(seq 1 10); do
    if docker exec hermes su -s /bin/sh hermes -c \
        "ssh -i /opt/data/ssh/key -o StrictHostKeyChecking=no -o ConnectTimeout=3 root@charlie 'echo OK'" 2>&1 | grep -q "^OK"; then
        echo "    ✅ SSH healthy (attempt $attempt)"
        HEALTH_OK=true
        break
    fi
    sleep 2
done
if ! $HEALTH_OK; then
    echo "    ❌ SSH failed after 5 attempts — check charlie logs"
fi

# ─── 12. Provider test ───
echo "[+] Testing API key (30s timeout)..."
if timeout 30 docker exec hermes hermes chat -q "reply with only: OK" > /tmp/barbarossa-provider-test.txt 2>/dev/null; then
    if grep -q OK /tmp/barbarossa-provider-test.txt 2>/dev/null; then
        echo "    ✅ Provider $HERMES_PROVIDER working"
    else
        echo "    ⚠️  Provider responded but without OK — may work, check logs"
        head -3 /tmp/barbarossa-provider-test.txt | sed 's/^/    /'
    fi
else
    echo "    ❌ Provider test failed — check API key and connectivity"
    echo "    Run: docker logs hermes --tail 30"
fi
rm -f /tmp/barbarossa-provider-test.txt

# ─── 13. Gateway status ───
echo "[+] Checking gateway..."
docker exec hermes hermes gateway status 2>/dev/null || true

echo ""
echo "╔════════════════════════════════════════╗"
echo "║  Setup complete!                       ║"
echo "╠════════════════════════════════════════╣"
echo "║  View logs:                            ║"
echo "║    docker compose logs -f hermes       ║"
echo "║    docker compose logs -f charlie       ║"
echo "║                                        ║"
echo "║  SSH into charlie:                      ║"
echo "║    ssh -i $KEY_PATH root@localhost \\   ║"
echo "║      -p 2222                           ║"
echo "║    VM_KEY=$KEY_PATH ./charlie/vm.sh \\   ║"
echo "║      check                             ║"
echo "║                                        ║"
echo "║  Setup log saved to:                   ║"
echo "║    setup.log                           ║"
echo "╚════════════════════════════════════════╝"
