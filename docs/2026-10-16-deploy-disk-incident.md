# Barbarossa — Disco cheio no host OVH (incidente de deploy)

> Registro para agentes: por que o redeploy `65b9af02` falhou no meio da
> extração, como o host foi recuperado e como evitar recorrência.

**Status:** resolvido em 2026-10-16; o redeploy `65b9af02` entrou em produção no
mesmo dia.

## Sintoma

O redeploy `65b9af02` (run `38921489308`) falhou no step "Cut over and smoke
test" durante o `docker pull`, com `no space left on device` em
`/var/lib/containerd` (extração de layer da imagem do Forge). O pull acontece
**antes** de qualquer mudança de runtime (snapshot de rollback e cutover vêm
depois), então a release `9668ec88` continuou rodando saudável — não houve
rollback porque nada tinha sido commitado.

## Causa raiz

1. O host (38 GiB, `/dev/sda1`) estava a 95% (2.1 GiB livres).
2. Cada deploy retém a geração anterior: tags
   `barbarossa-rollback-*:release.<id>` + diretórios em
   `~/.config/barbarossa/runtime/rollback/` — a coleta é manual.
3. A imagem do Forge cresceu com a lane OpenCode (`@opencode/cli` somado aos
   CLIs npm já existentes), ≈3 GiB por geração; o pull novo não cabia no espaço
   livre.

Inventário no momento (por ID de imagem): geração `8ccefba` (rollback "deployed"
de 09/10), geração `a379e01` (órfã do deploy frustrado da lane) e
`nousresearch/hermes-agent` pinada por digest (3 tags, 1 ID — não era dangling
real e não liberava espaço).

## Resolução

- Removidas as gerações obsoletas: forge/recon `8ccefba` (+ tags de rollback
  `release.Z9txAXC1`) e forge/recon `a379e01` → **7.95 GiB liberados**
  (36G→29G usados; 8.9 GiB livres).
- Mantidas: release corrente `9668`, o rollback ativo (`release.BSXPCKiK`) e a
  imagem de recon `65b9af` já puxada (evitando re-download).
- Rerun: `gh run rerun 38921489308 --failed` → deploy verde em 5m36s, smoke
  completo (incluindo `verified code.opencode` ×2).

## Prevenção

- `scripts/deploy-runtime-files.sh`: **preflight de espaço** no filesystem do
  Docker (`DockerRootDir`) — exige ≥4 GiB (default; `BARBAROSSA_MIN_FREE_KB`
  ajusta) antes de qualquer pull e falha antes de tocar em arquivos de
  runtime. O limite cobre o delta comum de uma imagem; troca de digest do
  Hermes pode exigir mais.
- `scripts/prune-rollback-images.sh`: coleta operacional (dry-run por padrão;
  `--apply` executa) que mantém a release de rollback mais nova e remove
  diretórios antigos + tags de imagem que só eles referenciam. Nunca toca
  containers em execução, tags da release retida, nem imagens fora de
  `barbarossa-*`; recusa-se a rodar com deploy lock presente. **Não** é chamado
  pelo deploy — o teste `tests/infra-regression.sh` garante que o helper segue
  fora do caminho de update (que continua sem cleanup destrutivo).
- Operação: quando o preflight acusar espaço, rodar o helper (`--apply`) e
  repetir o deploy.

## Evidência

- Log do pull que falhou: `gh run view 38921489308 --log --job 117048491257`
  (extração de layer abortada por ENOSPC).
- Antes/depois da limpeza: `docker system df` reclaimable 10.32GB → 2.99GB;
  `df -h /` 2.1 GiB → 8.9 GiB livres.
- Rerun verde: `65b9af02` ativo (`docker inspect` dos containers), rollback
  retido em `rollback/release.YVc6iCSS`, disco ~6.5 GiB livres após o deploy.
- Contexto do deploy anterior (credencial Codex):
  `docs/2026-10-16-codex-auth-persistence.md`.
