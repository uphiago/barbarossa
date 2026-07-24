#!/command/with-contenv sh
# Sync custom recon skills from GitHub on every container start.
# Runs after 02-reconcile-profiles (built-in skills sync).
set -e

SKILLS_REPO="${SKILLS_REPO:-https://github.com/uphiago/recon-skills.git}"
SKILLS_DEST="${HERMES_HOME:-/opt/data}/skills"

echo "[sync-recon-skills] Cloning ${SKILLS_REPO}..."

rm -rf /tmp/recon-skills
git clone --depth 1 "$SKILLS_REPO" /tmp/recon-skills 2>&1

COUNT=0
SKILL_DIRS=$(find /tmp/recon-skills -maxdepth 4 -type f -name SKILL.md -exec dirname {} \;)
for dir in $SKILL_DIRS; do
  name=$(basename "$dir")
  [ "$name" = "recon-skills" ] && continue
  [ "$name" = ".git" ] && continue
  cp -r "$dir" "$SKILLS_DEST/$name"
  COUNT=$((COUNT + 1))
done

chown -R hermes:hermes "$SKILLS_DEST"
echo "[sync-recon-skills] Done: ${COUNT} skills synced"

rm -rf /tmp/recon-skills
