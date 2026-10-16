# Barbarossa — Persistência da credencial Codex (incidente e correção)

> Registro para agentes: por que o smoke do deploy falhou em 2026-10-16, o que
> foi corrigido e como rotacionar/recuperar a credencial do Codex.

**Status:** corrigido em 2026-10-16; aplicado junto com o redeploy da lane
OpenCode.

## Sintoma

O deploy `a379e01` (lane OpenCode) fez o cutover, o Hermes subiu saudável e o
MCP listou 16 tools (incluindo `code_opencode`), mas o smoke morreu na primeira
checagem `code.delegate`:

```
ERROR codex_login::auth::manager: Failed to refresh token: Your access token
could not be refreshed because your refresh token was already used.
Please log out and sign in again.
```

O rollback automático restaurou a release anterior (comportamento correto).

## Causa raiz

1. Credenciais ChatGPT (`auth_mode: chatgpt`) usam refresh token com rotação e
   detecção de reuso: cada refresh consome o token anterior.
2. O entrypoint do Forge reinstalava o `auth.json` do mount a **cada boot**
   (`if [ -s source ]` sempre copiava), destruindo a cópia rotacionada que vive
   no volume `forge-codex-home`.
3. A mesma cadeia de refresh também era usada no workstation do operador; o
   refresh local consumiu o token que o cluster guardava.

Resultado: qualquer recriação de container restaurava um refresh token já
consumido → Codex quebrado até novo login. O incidente **não tinha relação com
a lane OpenCode**.

## Correção

`containers/forge/forge-entrypoint.sh` instala o `auth.json` do source apenas
quando o alvo não existe (bootstrap) ou quando o `last_refresh` do source é
mais novo que o do alvo (`refresh_is_newer()` — usa Python para comparar os
carimbos ISO). A cópia rotacionada no volume passa a sobreviver a recriações;
rotação deliberada via arquivo/secret continua funcionando.

## Runbook

- **Rotação (recomendado com login dedicado):**
  1. `CODEX_HOME=/tmp/cluster-codex codex login` (browser) — evita compartilhar
     a cadeia com o workstation.
  2. Substituir `${BARBAROSSA_RUNTIME_DIR:-$HOME/.config/barbarossa/runtime}/codex_auth.json`
     no host (escrita in-place; `install`/`cat >`, nunca `mv` por causa do bind
     mount dos containers).
  3. `gh secret set CODEX_AUTH_JSON_B64 < <(base64 -w0 arquivo)` — bootstrap/DR.
  4. Próximo deploy (ou `docker compose up --force-recreate forge`) instala o
     arquivo novo nos containers.
- **Recuperação em runtime (sem redeploy):**
  `docker exec barbarossa-forge-1 sh -c 'install -o forge -g forge -m 0600 /run/secrets/codex_auth_json /home/forge/.codex/auth.json'`
  (o secret montado reflete o arquivo do host em tempo real).
- **Bootstrap:** host novo recebe o arquivo pelo passo "Install worker
  credentials" do workflow ou manualmente; o alvo ausente sempre instala.

## Evidência (2026-10-16)

- Job `job_codex_01M52K9B5NFTDJGTR3R71S0ECC`: `result.json` com
  `"error":"command failed"` e o erro de refresh acima no `stderr.log`.
- `cmp` antes da correção: `/home/forge/.codex/auth.json` idêntico ao source
  (`last_refresh: 2026-10-02` — token já consumido em 13/10 no workstation).
- Após instalar a credencial fresca (`last_refresh: 2026-10-13`) e sincronizar
  o container: probe `codex exec --strict-config ...` como usuário `forge`
  retornou `BARBAROSSA_CODEX_OK`; host e volume com o mesmo hash (sem rotação).
- Redeploy `65b9af02` (2026-10-16): smoke completo verde (`verified
  code.delegate` ×2) com a credencial estável — mesmo hash (`ae3687…`) no
  volume do container, no arquivo do host e no secret `CODEX_AUTH_JSON_B64`
  (atualizado após o deploy).
