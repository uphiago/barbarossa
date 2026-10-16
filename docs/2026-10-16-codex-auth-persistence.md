# Barbarossa — Codex credential persistence (incident and fix)

> Agent record: why the deploy smoke check failed on 2026-10-16, what was fixed,
> and how to rotate or recover the Codex credential.

**Status:** fixed on 2026-10-16 and shipped with the OpenCode lane redeploy. The
install policy was hardened in the same window: stamps are compared as parsed
timestamps (not as text), equal or unusable stamps fall through to a file mtime
tiebreak, and `CODEX_AUTH_FORCE_INSTALL=1` forces a deliberate rotation.

## Symptom

Deploy `a379e01` (OpenCode lane) completed the cutover, Hermes came up healthy
and the MCP listed 16 tools (including `code_opencode`), but the smoke run died
on the first `code.delegate` check:

```
ERROR codex_login::auth::manager: Failed to refresh token: Your access token
could not be refreshed because your refresh token was already used.
Please log out and sign in again.
```

Automatic rollback restored the previous release (correct behaviour).

## Root cause

1. ChatGPT credentials (`auth_mode: chatgpt`) use rotating refresh tokens with
   reuse detection: every refresh consumes the previous token.
2. The Forge entrypoint reinstalled `auth.json` from the mount on **every boot**
   (`if [ -s source ]` always copied), destroying the rotated copy that lives in
   the `forge-codex-home` volume.
3. The same refresh chain was also used on the operator workstation; the local
   refresh consumed the token the cluster was holding.

Result: any container recreation restored an already-consumed refresh token →
Codex broken until a fresh login. The incident was **unrelated to the OpenCode
lane**.

## Fix

`containers/forge/codex-auth-sync.py` (shipped as
`/usr/local/bin/codex-auth-sync`, invoked by `forge-entrypoint.sh`) decides
whether the source credential may replace the copy in place:

1. the target is absent → install (volume bootstrap);
2. `--force` or a truthy `CODEX_AUTH_FORCE_INSTALL` → install;
3. both `last_refresh` stamps parse and differ → install only when the source is
   strictly newer;
4. stamps equal, absent or unusable → file mtime tiebreak, installing only when
   the source file is strictly newer on disk (which is what a deliberate
   rotation rewrites).

Stamps are compared as parsed timestamps, never as text:
`2026-10-16T15:08:13.500000Z` is newer than `2026-10-16T15:08:13Z`, while a
lexicographic comparison of those two strings claims the opposite. Stamps with
day granularity (for example `2026-10-13`) are equal for two rotations on the
same day, which is why case 4 falls through to the file mtime.

Every ambiguous case resolves to "keep the target": a used-up refresh token must
never clobber a rotated copy. The rotated copy in the volume therefore survives
container recreations, and `tests/test-codex-auth-sync.py` (21 cases) pins the
whole matrix inside the deploy gate.

## Runbook

- **Rotation (recommended with a dedicated login):**
  1. `CODEX_HOME=/tmp/cluster-codex codex login` (browser) — keeps the chain from
     being shared with the workstation.
  2. Replace `${BARBAROSSA_RUNTIME_DIR:-$HOME/.config/barbarossa/runtime}/codex_auth.json`
     on the host (write in place; `install`/`cat >`, never `mv`, because of the
     container bind mount).
  3. `gh secret set CODEX_AUTH_JSON_B64 < <(base64 -w0 file)` — bootstrap/DR.
  4. The next deploy (or `docker compose up --force-recreate forge`) installs the
     new file into the containers.
  - **Same-day rotation:** when the new file's `last_refresh` is not strictly
    newer than the copy in the volume (day-granularity stamps tie), the deploy
    keeps the volume copy on purpose. Either run the runtime recovery step below
    or force the install with `CODEX_AUTH_FORCE_INSTALL=1`.
- **Runtime recovery (no redeploy):**
  `docker exec barbarossa-forge-1 sh -c 'install -o forge -g forge -m 0600 /run/secrets/codex_auth_json /home/forge/.codex/auth.json'`
  (the mounted secret mirrors the host file live).
- **Bootstrap:** a new host receives the file through the workflow's "Install
  worker credentials" step or manually; an absent target always installs.

## Evidence (2026-10-16)

- Job `job_codex_01M52K9B5NFTDJGTR3R71S0ECC`: `result.json` with
  `"error":"command failed"` and the refresh error above in `stderr.log`.
- `cmp` before the fix: `/home/forge/.codex/auth.json` identical to the source
  (`last_refresh: 2026-10-02` — a token already consumed on the workstation on
  13/10).
- After installing the fresh credential (`last_refresh: 2026-10-13`) and syncing
  the container: the `codex exec --strict-config ...` probe as user `forge`
  returned `BARBAROSSA_CODEX_OK`, with the host and the volume holding the same
  hash (no rotation).
