# Barbarossa — Capacidade da lane OpenCode (swarm de subagentes)

> Registro para agentes: resultado do teste de estresse pedido pelo operador em
> 2026-10-16 (host de produção, Forge release `e4934d6`), com números medidos,
> os limites reais da máquina e o protocolo de despacho recomendado para o
> Hermes. Nenhuma configuração de deployment foi alterada.

**Status:** teste concluído em 2026-10-16. Lane segue como estava; achados
abaixo valem como orientação operacional.

## Método

Cada rodada = 1 job `code.opencode` (a lane admite um job por vez) cujo
orquestrador lançou N subagentes `tester` em modo **blocking**, cada um
queimando CPU por 2×20 s (`timeout 20 bash -c 'while :; do :; done'`,
exit 124 = `timeout` matou o loop no teto de 20 s, o comportamento esperado),
escrevendo o transcript cru em `outputs/shard-<i>.txt`, com consolidação em
`outputs/final.md`. Coleta externa a cada ~4 s: `docker stats` do Forge, load e
memória do host.

Template de prompt confiável (versão usada, com `<N>` e `<tarefa>`):

```text
Launch exactly <N> subagents, all with the tester role, as BLOCKING tasks
launched together in parallel. Do NOT use background mode. Do NOT end your
turn until every subagent has reported back and outputs/final.md exists.
Give each subagent index i this task: <tarefa>. Write the full raw transcript
to outputs/shard-i.txt via shell redirection and return it in your reply.
Only after ALL <N> subagents have reported, write outputs/final.md with one
line per subagent plus your own final snapshot. Return a short summary.
```

## Resultados (limites do Forge: 1.5 vCPU, 1408 MiB, 384 PIDs)

| Rodada | Subagentes | Pico mem Forge | Pico PIDs | Pico load (2 vCPU) | Mín. host livre | Duração do job |
| --- | --- | --- | --- | --- | --- | --- |
| N=4  | 4 (+1 orq.)  | 504 MiB | 36  | 2.3  | 2.04 GiB | 109 s |
| N=10 (background) | 10 (+1) | 500 MiB | 24  | 1.4  | 2.01 GiB | 37 s ⚠ *sem artefatos* |
| N=10 | 10 (+1) | 550 MiB | 54  | 1.9  | 2.02 GiB | 125 s |
| N=14 | 14 (+1) | 586 MiB | 70  | 8.0  | 1.95 GiB | 137 s |
| N=20 | 20 (+1) | 612 MiB | 102 | 11.1 | 1.93 GiB | 153 s |
| N=32 | 32 (+1) | 666 MiB | 106 | 12.9 | 1.87 GiB | 276 s |
| N=48 | 48 (+1) | 652 MiB | 130 | 13.8 | 1.87 GiB | 285 s |
| N=64 | 64 (+1) | 595 MiB | 55  | 7.3  | 1.92 GiB | 659 s |

Evidência (job dirs retidos em `/workspace/jobs`): N=10
`job_opencode_01M52WBT8V2TEDFK1ZJJEZ6KHZ`, N=14
`...01M52WGN6ZS71DW12XAZ33ZP6W`, N=20 `...01M52WP4AHYX0RX1NH2C8S0RKG`, N=32
`...01M52WVFHY5APQP3QGTH9DWD77`, N=48 `...01M52X5403TNRSDP63WN4RJ2W9`, N=64
`...01M52XM3AQ1FP4959GFMP7BXR1` — cada um com `outputs/final.md` +
`outputs/shard-<i>.txt` por subagente, todos `BURN1_EXIT=124`/`BURN2_EXIT=124`.

## Achados

1. **Concorrência prática ≈ 10 subagentes por vez.** É a política do
   orquestrador ("up to ten"); em N=64 o modelo explicitamente organizou 7
   ondas de 10/10/10/10/10/10/4. Em N≥32 houve lançamento escalonado (spread
   de início de ~100–125 s entre shards).
2. **Provider: sem rate-limit durante o teste; throttling depois.** Zero HTTP
   429 nas rodadas (até 64 subagentes + orquestrador por job; o único "429" nos
   logs era dígito de timestamp). Porém ~50 min após a janela (18:55–18:59Z),
   smokes `code.opencode` passaram a falhar em ~7 s com
   `Error: Rate limit exceeded. Please try again later.` — o free tier throttla
   após uso intenso. Tratar como transitório: aguardar alguns minutos e
   retentar, e/ou cair para `code_delegate`.
3. **A máquina nunca foi o gargalo.** Pior momento do Forge: ~666 MiB de
   1408 MiB e 130 de 384 PIDs; host nunca abaixo de 1.87 GiB livres; zero OOM
   (kernel e container), zero restart, swap estável.
4. **Trampa de protocolo (job "succeeded" vazio).** Se o orquestrador lança
   subagentes em background e encerra o turno, o `opencode run`
   não-interativo termina o job sem consolidar: status `succeeded`, exit 0 e
   **zero artefatos** (falso verde; ocorreu no N=10 background, 37 s de job).
   Com blocking + "não encerre o turno até `outputs/final.md` existir" o
   resultado fica íntegro em todos os N testados.
5. **Acima de 10, o custo é sequencial.** ~90–95 s por onda (N=64: 659 s).
   O timeout default do job (2700 s) cobre ~N=128 em ondas de 10 com folga.
6. **Contenção de CPU aparece no wall-clock.** Sob ondas cheias há fila de CPU
   (deltas por shard esticados até ~115 s no N=32), mas tudo completa: a cota
   de 1.5 vCPU limita throughput, não largura.

## Protocolo de despacho recomendado (Hermes)

- Prompts de fan-out devem exigir: subagentes **blocking** (nunca background);
  "não encerre o turno até `outputs/final.md` existir"; evidência por
  subagente em `outputs/shard-<i>.txt` quando a execução precisa ser auditável.
- Tratar **`succeeded` sem `outputs/final.md` como despacho falho** e retentar
  com a instrução explícita — a lane ainda não impõe a existência do artefato.
- Uso normal: até 10 concorrentes (default documentado) — confortável e rápido
  (`~2 min` para 10 shards sintéticos).

## Escala

- Mais largura real de CPU: subir `BARBAROSSA_FORGE_CPUS`/`_MEMORY` (o host tem
  2 vCPU / 3.7 GiB; o Forge hoje usa 1.5 vCPU / 1408 MiB) ou mover para host
  maior. Estimativa sintética: memória ~10–15 MB por sessão, ou seja, o teto do
  container só apareceria bem acima de 100 sessões concorrentes; trabalho real,
  com contextos grandes, consome mais por sessão.
- Jobs simultâneos na mesma lane não existem por design (lock exclusivo por
  lane): paralelismo = subagentes em ondas dentro de um job.
- Custo residual: ~600 B por shard; a retenção histórica de jobs estava em
  ~315 MB no workspace ao fim dos testes.
