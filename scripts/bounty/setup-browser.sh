#!/bin/sh
# Point the browser harness at a real Chromium instead of a minimal engine.
#
# The bundled browser backend can be a lightweight engine (e.g. lightpanda) that cannot execute a
# production single-page application. Heavy sites then time out mid-`Runtime.evaluate` and it looks
# like the target is broken. This installs Chromium for Testing via Playwright and wires it in.
#
# Idempotent: safe to re-run. Does not touch the running gateway.
set -eu

prefix="${1:-/opt/data}"
browsers="${BROWSERS_DIR:-$prefix/browser}"
venv="${VENV_DIR:-$prefix/bounty-tools/.venv}"
bindir="${BIN_DIR:-$HOME/.local/bin}"

command -v uv >/dev/null 2>&1 || { printf 'uv is required\n' >&2; exit 1; }

# 1. Client library + browser binary (no root needed; installs under $browsers).
if [ ! -x "$venv/bin/python" ]; then
  uv venv "$venv" --python 3.13
fi
uv pip install --python "$venv/bin/python" playwright curl_cffi >/dev/null

mkdir -p "$browsers"
PLAYWRIGHT_BROWSERS_PATH="$browsers" "$venv/bin/python" -m playwright install chromium

# 2. Locate the binary the harness will accept.
chrome="$(find "$browsers" -maxdepth 3 -type f -name chrome -perm -u+x 2>/dev/null | head -1)"
[ -n "$chrome" ] || { printf 'chromium binary not found under %s\n' "$browsers" >&2; exit 1; }

# 3. The harness resolves BH_CHROME_PATH, then CHROME_PATH, then these names on PATH.
mkdir -p "$bindir"
ln -sf "$chrome" "$bindir/chromium"
ln -sf "$chrome" "$bindir/google-chrome"

# 4. The daemon also loads .env from its workspace; write it there so a restart picks it up.
ws_env="$(find "$prefix/cache/browser-use/workspace" -maxdepth 2 -name .env -print -quit 2>/dev/null || true)"
if [ -n "$ws_env" ]; then
  printf 'BH_CHROME_PATH=%s\n' "$chrome" > "$ws_env"
else
  for d in "$prefix/cache/browser-use/workspace"/*/; do
    [ -d "$d" ] && printf 'BH_CHROME_PATH=%s\n' "$chrome" > "${d}.env"
  done
fi

printf 'chromium: %s\n' "$chrome"
"$chrome" --version 2>/dev/null || printf 'warning: binary did not report a version\n'
printf 'symlinks: %s/chromium %s/google-chrome\n' "$bindir" "$bindir"
printf 'next: the harness picks it up on its next start; verify with Browser Automation and\n'
printf '      navigate to any page, then read navigator.userAgent (expect HeadlessChrome/).\n'
