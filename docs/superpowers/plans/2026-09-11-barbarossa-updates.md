# Barbarossa — Updates e correções Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Atualizar os componentes usados pelo Barbarossa, corrigir os problemas encontrados e preservar DeepSeek V4.1 Flash como principal, delegação para Flash/Codex e continuidade pelo Telegram.

**Architecture:** Hermes continua orquestrando Forge e Recon pelo router MCP. Preparar e testar imagens e bundle antes de substituir os serviços; preservar os volumes, a configuração efetiva e uma release anterior recuperável.

**Tech Stack:** Docker Compose, Hermes, DeepSeek, Codex CLI, Node/npm, uv/PEX, router Python e ferramentas Recon.

**Status:** execução autorizada e em andamento em 2026-09-11. Código e imagens candidatos preparados em worktree isolado; produção ainda usa a release anterior. Os estados abaixo distinguem implementação local, validação e aplicação. Evidências operacionais e credenciais permanecem fora do Git.

---

## 1. Demanda e limites deste backlog

| Demanda | Como será atendida |
| --- | --- |
| Focar no Barbarossa | Inventário e atualizações dos seus três serviços, router e ferramentas de build usadas por eles. |
| Saber o que precisa atualizar/corrigir | T01 produz uma matriz de versão instalada, candidata, origem, compatibilidade e decisão. |
| DeepSeek principal orquestrando Flash ou Codex conforme configurado | T03 preserva o modelo principal, herança/overrides dos filhos e perfil Codex; T08/T09 comprovam as duas formas de delegação. |
| Conversar pelo Telegram e continuar o trabalho entre sessões | T07 preserva estado e pastas existentes; T09 verifica mensagens, consulta de jobs e retomada do contexto. |
| Organizar o trabalho antes de aplicar | Cada task abaixo tem prioridade, dependências, checklist e aceite. Esta revisão altera apenas o plano. |

A continuidade das pastas de ambiente existentes faz parte da manutenção.
Criar uma campanha nova, ampliar escopo de bounty ou iniciar exploração contínua
são demandas próprias, fora desta release de updates. Os testes usarão dados
sintéticos e recursos de teste controlados.

## 2. O que a revisão corrigiu

| Proposta anterior | Correção baseada no código e na demanda |
| --- | --- |
| Tratar a diferença de digest Hermes como deriva remota inexplicada | O checkout local está em `631fdcb`, e a referência local `origin/main` está em `1011a53`, quatro commits à frente. Essa referência já contém o digest Hermes relatado em execução. Primeiro reconciliar a base; só então identificar diferenças remotas restantes. |
| Investigar Vercel/Supabase como possíveis instalações avulsas | O Dockerfile em `origin/main` já instala ambos, além de uv; o entrypoint instala Specify. São componentes a inventariar, preservar e tornar reproduzíveis. |
| Usar o /tmp do Forge como bloqueio para qualquer build | Esse tmpfs afeta os jobs dentro do Forge. Builds no host ou no CI têm armazenamento próprio, que precisa de medição separada. |
| Apagar todos os caches bunx por wildcard | Identificar jobs e arquivos em uso; limpar somente entradas comprovadamente descartáveis depois de liberar o worker. |
| Rodar `setup.sh` como build ou atualização gradual | O script recria chaves e executa `compose down`. Removido do procedimento de atualização da instalação existente. |
| Conservar imagens anteriores usando o deploy atual | `deploy-runtime-files.sh` derruba serviços, recria chaves e chama limpeza de imagens antes do smoke do workflow. T07 precisa corrigir essa sequência para permitir rollback. |
| Tratar smoke dos workers como prova de DeepSeek/Telegram | O smoke chama o router diretamente. Sua tarefa com subagente é interna ao Codex. Ele não comprova uma delegação nativa Flash nem a entrega de mensagens pelo Telegram. |
| Atualizar dependências Python apenas com `uv lock --upgrade-package` | As diretas usam versões exatas em `pyproject.toml`. Para alterá-las, revisar esse arquivo e o lockfile; conferir se o teste do PEX executou sem skip. |
| Exigir todos os upgrades e mais verificações genéricas no CI | Atualizar o que tiver origem e compatibilidade verificadas; focar o CI nos testes reais das imagens e do gateway. Uma atualização opcional adiada não bloqueia a release principal. |
| Publicar inventário operacional no repositório | Manter evidência operacional e backups fora do Git, conforme `../AGENTS.md`. O plano contém apenas informações de código e decisões sem dados do ambiente. |

Estas conclusões vêm de leitura do repositório e das referências Git locais.
Não houve nova consulta ao servidor ou aos registries nesta revisão.

## 3. Fila de tasks e dependências

P0 corrige um problema operacional ou prepara a atualização da instalação;
P1 entrega a atualização e sua validação; P2 é atualização condicional.

| ID | Prioridade | Task | Depende de | Status |
| --- | --- | --- | --- | --- |
| T01 | P0 | Reconciliar código e fechar inventário | — | Em validação |
| T02 | P0 | Resolver ENOSPC e uso de caches do Forge | T01 | Em validação |
| T03 | P1 | Atualizar Hermes preservando DeepSeek e delegação | T01 | Em validação |
| T04 | P1 | Atualizar Forge e tornar suas CLIs reproduzíveis | T01; coordenar com T02 | Em validação |
| T05 | P1 | Atualizar Recon, base e templates utilizados | T01 | Em validação |
| T06 | P2 | Auditar e atualizar dependências do router quando necessário | T01; compatibilidade com T03 | Concluída localmente; aplicação em T09 |
| T07 | P0 antes do deploy | Preparar backup, atualização e rollback | T01 | Em execução |
| T08 | P1 | Validar a combinação escolhida para a release | T02–T07, conforme componentes incluídos | Em validação |
| T09 | P1 | Aplicar a release e comprovar continuidade no Telegram | T08 | Bloqueada por capacidade do host e conclusão de T07/T08 |

### Pendências verificadas em 2026-09-11

| Task | Evidência já obtida | O que ainda falta |
| --- | --- | --- |
| T01 | Base remota reconciliada, alterações locais preservadas; candidatos consultados em fontes oficiais. | Consolidar a matriz final de versões/decisões e terminar o inventário dos dados auxiliares e agendamentos. |
| T02 | Cache temporário por job implementado; testes de sucesso/falha comprovam limpeza sem remover outputs. | Repetir instalação sintética pela rota MCP, medir consumo e aplicar a correção ao worker de produção após drenagem. |
| T03 | Hermes candidato inicia; normalização de `deepseek-flash` validada; chamada ao principal e execução do filho Flash observadas. | Confirmar entrega do resultado do filho ao principal no fluxo persistente. O ensaio CLI oneshot executou o filho, mas a retomada da sessão não recebeu a conclusão. Isso ainda não foi atribuído ao gateway de produção. |
| T04 | Imagem Forge construída; CLIs fixadas; Specify instalado durante o build; job real do Codex concluiu no ambiente isolado. | Completar o ensaio com HOME/volume preexistente e as operações locais previstas para as CLIs. |
| T05 | Binários selecionados atualizados com checksums oficiais; imagem Recon construída. | Inventariar templates usados, concluir os checks ampliados das CLIs e o caso sintético contra fixture controlada. |
| T06 | Dependências e lockfile atualizados; suíte do router e teste do PEX aprovado sem skip; bundle executado no Hermes candidato. | Implantação e verificação em produção pertencem à T09. |
| T07 | Scripts preservam chaves, fontes, PEX e imagens anteriores; testes simulam falhas de download, startup e smoke. | Concluir backup consistente, drenagem coordenada, ensaio completo de restauração de volumes e procedimento operacional. |
| T08 | Cluster isolado em execução; worker/configuração/gateway/deploy testados; Codex real aprovado. | Fechar regressão de infraestrutura (há expectativa antiga de instalação do Specify), revisão final do CI, fluxo completo Flash/MCP/Codex, mídia/Recon e persistência após reinício. |
| T09 | Nenhum serviço de produção substituído. | Resolver capacidade do host, fixar/publicar release, instalar, validar Telegram/agendamentos/estado e observar por 30 minutos. |

A capacidade do host para manter release nova e rollback está insuficiente.
Uma alteração de swap foi proposta separadamente por afetar o servidor inteiro;
ela não foi executada e continua dependendo de autorização específica. Essa
dependência não impede concluir código, testes locais e documentação.

**Sequência:** T01 → preparação de T02–T07 → T08 → T09.
T03/T04/T05/T06 podem ser preparadas separadamente; T03 e T06 precisam ser
compatíveis entre si. Compose, testes e CI são arquivos compartilhados e devem
ser integrados em uma única revisão coerente.

T06 pode terminar com “manter versão atual”, desde que haja justificativa.
T07 bloqueia qualquer deploy até existir uma forma testada de voltar à release
anterior. Limpeza do Forge não bloqueia leitura de código nem build isolado.

## 4. Tasks propostas

### T01 — Reconciliar código e fechar inventário

**Problema:** o plano anterior partiu de um checkout anterior à instalação
relatada e tratou versões candidatas como destinos obrigatórios.

**Resultado esperado:** uma base de trabalho que inclui as mudanças já
publicadas e preserva o patch local do DeepSeek, com decisão para cada update.

**Arquivos:** `README.md`, `hermes.env.example`,
`config/hermes/gateway_entrypoint.py`, `tests/test-hermes-configure.py`,
`tests/infra-regression.sh`, `docker-compose.yml`, Dockerfiles dos workers,
`router/pyproject.toml` e `.github/workflows/build-deploy.yml`.

- [ ] **T01.1** Preservar mudanças tracked e untracked em cópia privada persistente; preparar branch/worktree a partir da revisão remota confirmada, reaplicando as mudanças necessárias. Conferir que a configuração DeepSeek e o volume `forge-home` foram preservados.
- [ ] **T01.2** Comparar fonte, artefatos publicados e instalação efetiva: commit, plataforma, digest da imagem, versão do binário, hash do PEX e mounts. Distinguir digest de índice multiarch, manifesto de plataforma e ID local da imagem.
- [ ] **T01.3** Reconfirmar candidatos nos registries e releases oficiais. Registrar origem, data, restrições de runtime e decisão: atualizar, manter ou adiar com motivo.
- [ ] **T01.4** Inventariar separadamente pacotes da distribuição, ambiente Python do Hermes, router, CLIs globais do Forge e dependências dos projetos. Consultas devem usar cache de auditoria isolado.
- [ ] **T01.5** Identificar jobs ativos, tarefas agendadas, sessões e volumes/pastas de estado a preservar, usando metadados sem imprimir configurações completas ou evidências privadas.

**Aceite:** cada componente tem origem e destino identificado; mudanças locais
estão preservadas; diferenças entre fonte e instalação estão explicadas.
Dados privados e backups ficam fora do Git.

**Candidatos herdados da consulta anterior — reconfirmar, não instalar automaticamente:**

| Componente | Instalação relatada | Candidato relatado | Decisão necessária |
| --- | --- | --- | --- |
| Hermes | 0.20.1 | 0.21.1 / v2026.9.7 | Release, plataforma, normalização do modelo e compatibilidade com router |
| Codex CLI | 0.145.0 | 0.154.0 | Flags/configuração e perfil de modelo em uso |
| npm no Forge | 11.16.0 | 12.0.2 | Migração major e compatibilidade com Node; não obrigatória |
| Vercel / Supabase | 59.1.3 / 2.114.0 | 59.16.0 / 2.117.0 | Versão fixa e método de instalação suportado |
| uv / Specify | Instalação efetiva pendente de confirmação | Consultar releases oficiais | Versão, usuário, PATH e instalação persistente |
| dnsx / httpx | 1.2.3 / 1.9.0 | 1.3.0 / 1.12.0 | Binários e flags usados pelo Recon |
| nuclei / subfinder | 3.9.0 / 2.14.0 | 3.11.1 / 2.16.0 | Binários, configurações e templates compatíveis |
| katana / tlsx | 1.6.1 / 1.2.2 | 1.7.0 / 1.3.0 | Runtime não-root e formatos de saída |
| naabu / amass / ffuf | 2.6.1 / 5.1.1 / 2.1.0 | Sem candidato novo confirmado neste plano | Manter se a reconsulta não justificar mudança |
| Node 24 / Alpine 3.22 | Digests fixados no código | Atualização de base relatada | Comparar o mesmo tipo de digest e a mesma plataforma |
| Python / router / ferramentas de CI | Pins em fontes e lockfile | Inventariar | Separar dependências de aplicação das geridas por apt/apk |

### T02 — Resolver ENOSPC e uso de caches do Forge

**Problema:** a auditoria anterior relatou 94% de ocupação no tmpfs de 128 MB
e falha de consulta npm por falta de espaço. Limpeza pontual não explica nem
resolve uma possível recorrência.

**Resultado esperado:** jobs de instalação e execução com margem de espaço
medida, sem perder arquivos de trabalhos em andamento.

**Arquivos:** `docker-compose.yml`, `containers/forge/forge-entrypoint.sh`,
`containers/shared/worker-rpc.py`, `tests/test-worker-rpc.py` e
`tests/container-integration.sh`, conforme a causa reproduzida.

- [ ] **T02.1** Medir bytes e inodes do tmpfs, espaço do host/volumes e consumo dos caches. Correlacionar entradas com jobs/processos ativos; não assumir que os 94% continuam iguais.
- [ ] **T02.2** Liberar o worker para manutenção e remover apenas caches identificados como dispensáveis e sem uso. Preservar workspace, autenticação e resultados.
- [ ] **T02.3** Reproduzir uma instalação sintética pela mesma rota MCP, usuário, HOME/PATH e limites do job que falhou. Determinar se basta limpar ou se é preciso definir localização/limite de cache; ampliar tmpfs somente com medição de memória.
- [ ] **T02.4** Se houver mudança de código/configuração, verificar repetição do job e execução simultânea permitida. Registrar pico de consumo e margem restante.

**Aceite:** o caso representativo conclui sem ENOSPC, preserva artefatos e não
consome indefinidamente o espaço após repetições. O tamanho do tmpfs se baseia
no workload medido; não em um percentual arbitrário.

### T03 — Atualizar Hermes preservando DeepSeek e delegação

**Problema:** o gateway local altera uma API interna do Hermes para manter o
identificador `deepseek-flash`. Os testes de gateway atuais verificam anexos,
mas não executam esse caminho de inicialização.

**Resultado esperado:** Hermes atualizado com o DeepSeek solicitado como
principal, filhos Flash conforme a configuração e Codex no papel já definido.

**Arquivos:** `docker-compose.yml`, `config/hermes/gateway_entrypoint.py`,
`config/hermes/configure.py`, `hermes.env.example`,
`tests/test-hermes-configure.py`, `tests/test-hermes-gateway.py` e
`tests/infra-regression.sh`.

- [ ] **T03.1** Inspecionar a release escolhida e seu código de normalização antes de fixar o digest. Verificar se o suporte nativo tornou o patch dispensável ou se exige adaptação.
- [ ] **T03.2** Testar inicialização do gateway e normalização do modelo na imagem candidata. Preservar herança dos filhos quando não houver override e respeitar os overrides/limites existentes; não substituir silenciosamente por outro modelo.
- [ ] **T03.3** Atualizar pin, integração e expectativas dos testes em conjunto. Testar a configuração gerada e o entrypoint real; `hermes --version` sozinho não demonstra compatibilidade.
- [ ] **T03.4** Verificar o cliente MCP do novo Hermes com o PEX candidato. Fazer uma resposta sintética do modelo principal e uma delegação nativa Flash em ambiente separado da sessão de produção, registrando apenas metadados do provider/modelo efetivamente chamado.

**Aceite:** inicialização funciona, a chamada principal usa o identificador
solicitado, a delegação nativa usa a configuração esperada e o MCP conecta.
Manter ou retirar o patch depende dessa evidência.

### T04 — Atualizar Forge e tornar suas CLIs reproduzíveis

**Problema:** `origin/main` já instala Vercel/Supabase sem versão fixa e uv por
instalador mutável. Specify é instalado no boot com falhas suprimidas por
`|| true`; o sucesso do container não comprova sua disponibilidade ao job.

**Resultado esperado:** a mesma release produz o mesmo conjunto de CLIs e o
usuário do worker consegue executá-las.

**Arquivos:** `containers/forge/Dockerfile`,
`containers/forge/forge-entrypoint.sh`, `containers/shared/worker-rpc.py`,
`docker-compose.yml`, `.env.example`, `tests/container-integration.sh` e
`tests/test-worker-rpc.py`.

- [ ] **T04.1** Atualizar base Node dentro da linha escolhida e Codex CLI para os candidatos validados. Preservar modelo, reasoning e limites Codex existentes.
- [ ] **T04.2** Fixar as versões escolhidas de Vercel, Supabase e uv, verificando método de instalação e checksums disponíveis. Tratar npm 12 como decisão separada após validar engines e comandos usados.
- [ ] **T04.3** Confirmar a instalação de Specify sob o usuário e PATH reais do worker. Corrigir disponibilidade se houver falha reproduzida e substituir falha silenciosa por diagnóstico útil; manter uma origem/versionamento reproduzível.
- [ ] **T04.4** Testar as CLIs em imagem nova e com volume Forge já existente. Verificar se o volume mascara versões instaladas na imagem e garantir que a atualização não dependa de um volume vazio.
- [ ] **T04.5** Validar `code.delegate`, argumentos e configuração estrita do Codex e uma operação local simples de cada CLI. Usar fixtures, sem publicar aplicações ou mudar bancos de dados.

**Aceite:** as versões escolhidas estão fixadas, os jobs encontram as CLIs e
Codex respeita o perfil vigente. Atualização com volume preservado funciona;
nenhuma CLI ausente é anunciada como operacional.

### T05 — Atualizar Recon, base e templates utilizados

**Problema:** o conjunto inclui binários externos, pacotes Alpine e dados como
templates. Trocar somente a versão de Nuclei não comprova a disponibilidade ou
compatibilidade dos templates usados.

**Resultado esperado:** ferramentas atualizadas funcionando pelas rotas do
Recon e com integridade verificável.

**Arquivos:** `containers/recon/Dockerfile`,
`containers/shared/worker-rpc.py`, `docker-compose.yml`,
`tests/container-integration.sh`; documentação das ferramentas em uso.

- [ ] **T05.1** Atualizar os binários selecionados em T01. Comparar downloads com checksums oficiais ou assinatura publicada quando disponível, registrando procedência; calcular um hash local sozinho não autentica a origem.
- [ ] **T05.2** Atualizar a base Alpine na linha escolhida e reconstruir seus pacotes. Tratar bibliotecas Python geridas por apk como parte da distribuição, sem sobrescrevê-las com pip por causa de uma lista de versões do PyPI.
- [ ] **T05.3** Inventariar templates Nuclei e outras bases efetivamente utilizadas. Se presentes, registrar revisão/origem, localização gravável e compatibilidade; se ausentes, registrar isso sem incluir coleções não utilizadas.
- [ ] **T05.4** Testar versões, flags e saídas consumidas pelo worker, além de configurações/HOME sob usuário não-root e filesystem somente leitura.
- [ ] **T05.5** Executar um caso sintético contra fixture local; verificar capabilities Linux e redes existentes. Exercitar Tor somente por rota explícita, sem usá-lo como fallback.

**Aceite:** binários selecionados e dados necessários funcionam no ambiente
real do worker, com integridade e saída verificadas. Bater uma versão no banner
não é suficiente; nenhum alvo de bounty é usado na validação.

### T06 — Auditar dependências do router e do ambiente Python

**Problema:** o inventário de Python ainda não distingue adequadamente router,
Hermes e pacotes da distribuição. Updates do router podem afetar o contrato
com o cliente MCP da nova imagem Hermes.

**Resultado esperado:** dependências avaliadas e, quando houver update
justificado, PEX reproduzível e compatível com Hermes.

**Arquivos:** `router/pyproject.toml`, `router/uv.lock`,
`router/Containerfile.bundle`, `router/tests/` e
`.github/workflows/build-deploy.yml`.

- [ ] **T06.1** Auditar runtime e build/dev: asyncssh, mcp, pydantic, hatchling, pex, pytest e pytest-asyncio. Registrar também versão de uv e Python do build. Separar o ambiente interno do Hermes, atualizado preferencialmente com sua imagem.
- [ ] **T06.2** Para cada dependência direta selecionada, alterar a versão exata em `pyproject.toml` e regenerar `uv.lock`. Para transitivas, revisar o lockfile sem ampliar os upgrades além da mudança escolhida.
- [ ] **T06.3** Verificar scheduler, cancelamento, reconciliação de jobs, persistência e redaction nos testes existentes.
- [ ] **T06.4** Gerar o PEX seguindo o job `build-router` e executar `test_packaged_server.py` com as variáveis necessárias; validar também o bundle sob o Python da imagem Hermes candidata.

**Aceite:** dependências selecionadas têm compatibilidade demonstrada e o teste
do PEX executa sem skip. Se nenhum upgrade for necessário, registrar “manter”
e provar que o PEX atual funciona com a release proposta.

### T07 — Preparar atualização da instalação existente e rollback

**Problema:** os scripts atuais fazem teardown global e rotação de chaves;
o deploy limpa imagens antes do smoke. A etapa de upload substitui arquivos
montados nos containers antes da validação da nova release.

**Resultado esperado:** instalar a release testada e poder recuperar a anterior,
incluindo estado compatível, se houver regressão.

**Arquivos:** `scripts/deploy-runtime-files.sh`, `scripts/compose.sh`,
`.github/workflows/build-deploy.yml`, `tests/infra-regression.sh`,
`README.md`. Criar `tests/test-deploy-runtime.py` para verificar a sequência
operacional sem chamar Docker de produção.

- [ ] **T07.1** Definir cópia privada e consistente do estado Hermes, banco de jobs, configurações, credenciais existentes e volumes/pastas dos workers. Conferir mounts reais, espaço para a release anterior/nova e recuperação de um marcador sintético.
- [ ] **T07.2** Separar atualização de bootstrap. Baixar/verificar imagens e preparar PEX/fontes em diretório de release antes de alterar os arquivos ativos; manter controle SSH existente e volumes nomeados.
- [ ] **T07.3** Ajustar o caminho de upload/deploy para drenar jobs e substituir serviços de forma coordenada. Retirar do caminho normal de update o teardown global, rotação incondicional de chaves e limpeza de volumes legados.
- [ ] **T07.4** Retirar a limpeza de imagens do caminho anterior à validação. Reter explicitamente a release em uso e a anterior com fontes, imagens e PEX; mover a limpeza para depois da observação bem-sucedida.
- [ ] **T07.5** Testar com um substituto de Docker: falha de download não para serviços nem troca estado; falha de inicialização preserva os artefatos para rollback; imagens anteriores sobrevivem à falha do smoke.
- [ ] **T07.6** Ensaiar restauração em ambiente isolado, inclusive quando o Hermes candidato migrar dados. Documentar a sequência e a indisponibilidade esperada; não prometer atualização sem interrupção.

**Aceite:** rollback demonstrado antes de produção; serviços não são parados
por falha de pré-download; estado/credenciais e release anterior permanecem
recuperáveis. `setup.sh` fica restrito à criação inicial.

### T08 — Validar a combinação escolhida para a release

**Problema:** o CI atual constrói/publica workers sem executar o script de
integração deles; também não chama os testes de gateway. O smoke remoto deixa
lacunas na comprovação da orquestração.

**Resultado esperado:** a release candidata passa em testes de comportamento,
usando os mesmos artefatos que serão publicados.

**Arquivos:** `.github/workflows/build-deploy.yml`,
`tests/container-integration.sh`, `tests/infra-regression.sh`,
`tests/test-hermes-gateway.py`, `scripts/smoke-remote.sh` e
`router/tests/test_packaged_server.py`.

- [ ] **T08.1** Incluir testes de gateway e integração das imagens no fluxo de validação. Adaptar integração para testar artefatos já construídos e publicar/promover esses mesmos digests após aprovação dos checks.
- [ ] **T08.2** Rodar regressões de worker/configuração, secrets, Compose, router e PEX. Validar Compose com ambiente sintético completo, incluindo a variável que aponta para o arquivo Hermes; não imprimir o Compose expandido com credenciais.
- [ ] **T08.3** Iniciar o conjunto candidato com volumes de teste e configuração isolada. Verificar runtime, código, mídia quando afetada e Recon, além da conexão Hermes → MCP → worker.
- [ ] **T08.4** Exigir evidência de uma delegação nativa Flash e outra via `code.delegate`: chamada, status terminal e resultado. A resposta textual “OK” ou o modelo declarar seu próprio nome não comprova o roteamento.
- [ ] **T08.5** Testar reconciliação após reinício e consulta do mesmo job sem duplicar execução. Usar marcador sintético para verificar contexto/pasta persistente.
- [ ] **T08.6** Se houver bot de teste, verificar envio/recebimento nele. Sem bot de teste, registrar a checagem real do Telegram como etapa pós-deploy obrigatória da T09; nunca iniciar dois consumidores com o token de produção.

**Aceite:** artefatos selecionados aprovados em integração, modelo/delegação
comprovados por metadados de execução e estado persistente preservado. O smoke
do router e o teste do orquestrador têm evidências distintas.

**Comandos locais existentes, a partir da raiz do repositório:**

```bash
uv run --with pytest==9.1.1 --with pyyaml==6.0.3 pytest tests/test-worker-rpc.py tests/test-hermes-configure.py tests/test-hermes-gateway.py -q
tests/test-hermes-secret-stage.sh
uv run --with pyyaml==6.0.3 bash tests/infra-regression.sh
(cd router && uv sync --frozen && uv run pytest -q)
```

Esses comandos não iniciam deploy. O teste do PEX requer o bundle e as
variáveis previstas em `router/tests/test_packaged_server.py`; a suíte geral
pode pular esse teste sem elas. Builds de integração pertencem ao ambiente de
teste/CI, não ao tmpfs do Forge em produção.

### T09 — Aplicar a release e comprovar continuidade no Telegram

**Problema:** containers saudáveis não bastam para garantir que o usuário
consiga conversar, acompanhar jobs e retomar o trabalho no Barbarossa.

**Resultado esperado:** release instalada com DeepSeek principal, delegação
operacional e estado acessível entre sessões.

**Arquivos/artefatos:** workflow e scripts revisados em T07/T08, release
imutável aprovada, cópia privada de recuperação e documentação de operação.

- [ ] **T09.1** Fixar a revisão limpa e os digests testados. Conferir jobs ativos/agendados, parar a entrada de novos trabalhos durante a troca e preparar backup consistente; não cancelar trabalhos por conveniência.
- [ ] **T09.2** Publicar/aplicar pela etapa intencional de release prevista no repositório, usando o procedimento corrigido em T07. Criação de tag ou dispatch é ato de deploy, não consulta ou build de teste.
- [ ] **T09.3** Executar smoke de capacidades e conferir versões, modelo efetivo e recursos. Se houver falha de inicialização, modelo incorreto, perda de estado ou delegação quebrada, reverter e registrar diagnóstico.
- [ ] **T09.4** Validar no canal privado já usado pelo usuário: mensagem recebida, delegação Flash, delegação Codex e resposta entregue. Consultar o mesmo job/contexto em nova sessão e verificar um marcador na pasta de teste persistente.
- [ ] **T09.5** Confirmar que agendamentos existentes continuam sem duplicar execuções ou notificações. Registrar estado anterior/posterior; este update não cria um loop novo de exploração.
- [ ] **T09.6** Observar por pelo menos 30 minutos com casos sintéticos representativos: reinícios, falhas MCP/provider, ENOSPC e entrega de mensagens. Encerrar com versões instaladas, adiamentos e pendências informados ao usuário aqui.

**Aceite:** checagens de infraestrutura e fluxo real aprovadas, trabalhos e
pastas preservados, mensagens sem duplicação e release anterior recuperável.
Só depois da observação concluir a manutenção e liberar limpeza específica.

## 5. Entregas e acompanhamento

- [ ] Matriz de inventário/decisões concluída; versões candidatas reconfirmadas.
- [ ] ENOSPC resolvido ou causa delimitada com solução validada.
- [ ] Componentes selecionados atualizados; componentes mantidos/adiados justificados.
- [ ] DeepSeek principal, filhos Flash e rota Codex comprovados.
- [ ] CI, bundle e imagens testados sem skips indevidos.
- [ ] Atualização e rollback ensaiados com preservação de estado.
- [ ] Telegram, continuidade entre sessões e jobs verificados após aplicação.
- [ ] Relatório final entregue aqui; evidência operacional privada fora do Git.

Usar em cada task os estados **Proposta → Em execução → Em validação →
Concluída**. “Adiada” exige motivo e impacto; “Bloqueada” deve apontar a
dependência concreta. Atualizar checkboxes somente com evidência correspondente.

O documento organiza as propostas e seus critérios de aceite. Os comandos
operacionais de cada alteração serão fechados sobre o inventário da T01,
evitando transformar versões antigas ou condições não verificadas em um
roteiro de execução automática.
