# Barbarossa — Free tier do OpenCode: throttle, bounty mode e teto de instâncias cruas

> Registro para agentes: assinatura do rate-limit do free tier, o padrão
> "bounty" de retry do deploy (double-tap + watch) e as medições do teto real
> de instâncias cruas fora da lane ("canhão tora"). Complementa
> `docs/2026-10-16-opencode-swarm-capacity.md` (capacidade em ondas de
> subagentes) e `docs/2026-10-16-opencode-lane.md` (contrato da lane).

**Status (2026-10-16, ~20hZ):** free tier throttlado desde ~18:55Z; deploy de
`main` em espera pela cota (retry persistente armado); prod no release ativo
`a9cf79e` (rollback automático do deploy que falhou no smoke).

## A assinatura do throttle

- Erro: `Error: Rate limit exceeded. Please try again later.`
- Aparece no `stderr.log` do job; resultado `failed`, exit 1; morte em ~4–7 s
  (a primeira chamada de modelo morre). Idêntico em instâncias cruas (K=1
  medido: 4 s).
- É **provider-side**: um smoke de um prompt só falha igual — não é tamanho de
  prompt, concorrência da lane nem estado do Forge. O mesmo prompt passa quando
  a cota reabre. (Não confundir com o `403 FreeTierError` de acesso fora do
  CLI — outro gate.)
- **Deploy**: o gate de cutover (`scripts/smoke-remote.sh`) roda 2 smokes
  `code.opencode` (direto + subagente `explorer`). Com o tier fechado o deploy
  falha no smoke e o **rollback automático** restaura a prod (observado: run
  `38950051678`, sha `283f402`, smoke `job_opencode_01M5313D6R9KE1ZG32MB1G308Q`
  morto em ~7 s; prod de volta em `a9cf79e`). **Nunca bypassar o gate** —
  retentar é a solução; o rollback é a rede.

## Linha do tempo observada

| Janela (UTC) | Estado |
| --- | --- |
| 17:27–18:05 | teste de swarm (~65 sessões) — zero throttling |
| ~18:55 | primeira falha `Rate limit exceeded` |
| 18:55–20:15+ | throttling contínuo (sondas a cada ~5 min sempre limitadas) |

Hipótese: janela longa / cota anônima consumida pelo uso intenso; pode levar
horas (possivelmente até outro dia). Não há contador visível — só sondando.

## Bounty mode (retry persistente do deploy)

Padrão operado fora do Hermes, em 5 regras:

1. **Sonda** = 1 job `code.opencode` mínimo:

   ```text
   R submit --capability code.opencode --timeout-seconds 900 \
     --prompt "Reply with exactly BARBAROSSA_RETRY_OK." --wait
   ```

   Sucesso = `"status":"succeeded"` no JSON. A sonda exercita exatamente o gate
   que o deploy usa.
2. **Double-tap**: exigir **2 sucessos consecutivos** (90 s de intervalo) antes
   de qualquer dispatch — o tier pode oscilar e o deploy precisa de 2 smokes
   próprios; um sucesso isolado é sinal fraco.
3. **Buffer**: 60 s após o double-tap e então
   `gh workflow run build-deploy.yml -R uphiago/barbarossa --ref main`.
4. **Watch & retry (v2)**: após o dispatch, `gh run watch`; se o run não ficar
   verde (re-throttle no smoke é a falha mais comum), **voltar a sondar** em vez
   de desistir. Só encerra verde (ou no cap de 48 h).
5. **Cadência das sondas**: 5 min (primeiras 2 h) → 15 min (até 24 h) → 30 min
   (até o cap). Cadência agressiva **não** acelera a janela do provider — só
   gera ruído e job-litter (cada sonda cria um job real retido em
   `/workspace/jobs`; ~315 MB retidos ao fim do teste de swarm).

Estado em 2026-10-16: sondas 1–5 (19:53–20:14Z) todas throttladas; loop v2
(com watch & retry) armado e girando.

## Instâncias cruas fora da lane ("canhão tora")

Para medir o **teto real do container** — não o teto dos subagentes — rodamos
instâncias `opencode run` independentes via `docker exec`, fora do `flock` da
lane (jobs não são tocados). Ferramenta: `scripts/forge-ceiling-probe.sh`
(escada 2→4→6→8→12→16; para sozinha na primeira parede; artefatos em
`/tmp/tora-<ts>` no host e `/workspace/.tora/<ts>` no container).

Cada instância replica o contrato do worker: usuário `forge`, `HOME`/`TMPDIR`/
`XDG_*` próprios no workspace, config staged de
`/usr/local/share/barbarossa/opencode`, e:

```text
timeout 600 opencode run --standalone --auto --agent orchestrator \
  --model opencode/deepseek-v4.1-flash-free#low "<prompt>"
```

Medições (K=1 real, 2026-10-16 — instância morre por throttle em 4 s):

| Métrica | Valor medido |
| --- | --- |
| Memória **anon** por instância | **~288 MiB** (idle: 2.3 MiB) |
| PIDs por instância | ~21 (baseline 3 → 24) |
| Page cache residual | ~268 MiB (**reclamável**; não conta para OOM) |
| Parede de memória (1408 MiB) | **~4–5 instâncias** |
| Parede de PIDs (384) | ~18 instâncias (a memória chega antes) |

Contraste importante: no teste em ondas, 10 subagentes concorrentes ≈ 550–666
MiB **no total** (sessões dentro de um mesmo processo orchestrator). Instância
crua é um processo bun inteiro por unidade (~288 MiB cada). Os dois números são
válidos — medem coisas diferentes.

### Receitas de medição (host)

Cgroup v2 do container no host:

```bash
cid=$(docker inspect -f '{{.Id}}' barbarossa-forge-1)
cg=/sys/fs/cgroup/system.slice/docker-$cid.scope
cat $cg/memory.current $cg/pids.current
grep -E '^(anon|file) ' $cg/memory.stat        # anon = o que causa OOM
awk '/^oom_kill/{print $2}' $cg/memory.events  # kills do memcg (parede real)
awk '/^max /{print $2}' $cg/pids.events        # forks negados pelo limite
cat $cg/memory.peak $cg/pids.peak              # picos de vida do cgroup
```

Contar instâncias vivas tem pegadinha dupla: `docker top` sem a coluna PID
falha no daemon (`Couldn't find PID field in ps output`), e o wrapper `sh -c` +
`timeout` duplicam a linha do comando. Padrão ancorado que conta 1 por
instância:

```bash
docker top barbarossa-forge-1 -eo pid,args \
  | grep -E -c '[0-9]+ +timeout 600 /usr/local/bin/opencode run'
```

## Próximos passos

- Endurecer `scripts/smoke-remote.sh`: retry com backoff quando um smoke
  `code.opencode` falhar com `Rate limit exceeded` — o deploy deixa de ser
  flaky por humor do provider, **sem** afrouxar o gate (continua exigindo os
  dois smokes verdes).
- Quando o tier reabrir: além de deixar o deploy fechar, rodar a escada
  completa do `forge-ceiling-probe.sh` para fechar o teto de instâncias cruas
  (o ensaio ficou armado e validado em 2026-10-16, mas não disparou com o tier
  fechado).

## Referências

- `docs/2026-10-16-opencode-swarm-capacity.md` — capacidade em ondas de
  subagentes (o outro teto).
- `docs/2026-10-16-opencode-lane.md` — contrato da lane.
- `scripts/forge-ceiling-probe.sh` — sonda do teto de instâncias cruas.
