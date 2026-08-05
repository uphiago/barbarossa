# Orquestrando listmonk via Hermes Barbarossa

Guia de uso para gerenciar o listmonk (newsletter / mailing list) através do
Hermes Barbarossa.

## Arquitetura

```text
Você pede ao Hermes              Hermes (orquestrador)
"cria lista X"  ───────────────►  lê a skill barbarossa-listmonk
                                  │
                                  ▼
                        network_inspect (tool MCP)
                                  │
                                  ▼
                        Recon (worker) ──► http://172.19.0.4:9000/api/...
                                  │
                                  ▼
                        listmonk (container na mesma OVH)
```

- O **Hermes** planeja e roteia. Não faz chamada de rede direta.
- O **Recon** executa os `curl` contra a API do listmonk.
- O listmonk foi conectado às redes `hermes-recon` e `hermes-forge` do
  Barbarossa, então o Recon o alcança em `172.19.0.4:9000`.

## O que já está pronto

| Item | Estado |
|---|---|
| listmonk v6.2.0 rodando na OVH | ✅ `/opt/stacks/listmonk`, porta 9000 |
| PostgreSQL 17 (local) | ✅ porta 5433 no host |
| Recon alcança a API | ✅ testado, HTTP 200 |
| API user `hermes` + token | ✅ criado no banco (SHA-256 do token) |
| Skill `barbarossa-listmonk` | ✅ `skills/hermes/barbarossa-listmonk/SKILL.md` |
| Túnel SSH local 9000 | ✅ `http://localhost:9000` = dashboard |
| SMTP Google Workspace | ✅ validado com TLS e entrega real |
| Lista `Newsletter` | ✅ ID `3`, pública, double opt-in |
| Template editorial padrão | ✅ ID `5`, `Carta semanal — hiago.sh`; variante compacta com favicon e cancelamento |
| Variantes editoriais de teste | ✅ IDs `6`, `7`, `8`; favicon real, só cancelamento |
| Campanha de exemplo | ✅ ID `2`, permanece em `draft` (não foi disparada para a lista) |

## Acesso ao dashboard

Com o túnel ativo:

```bash
ssh ovh          # túnel com LocalForward 9000
# no navegador:
# http://localhost:9000
```

Login no dashboard: usuário **hiagod** (criado no primeiro acesso).

## SMTP e remetentes

As configurações SMTP ficam no banco e são administradas pelo dashboard em
**Settings → SMTP**; elas **não** ficam no `config.toml`. O usuário de API
`hermes` não deve receber permissão de Settings nem acesso à senha.

Configuração atualmente validada:

| Campo | Valor |
|---|---|
| Host | `smtp.gmail.com` |
| Porta | `465` |
| Auth protocol | `LOGIN` |
| Username SMTP | `hey@hiago.sh` (conta Workspace real) |
| TLS | `SSL/TLS` (`tls_type: TLS`) |
| From padrão da newsletter | `Newsletter <newsletter@hiago.sh>` |
| From addresses | `newsletter@hiago.sh`, `hey@hiago.sh` |

`newsletter@hiago.sh` é um grupo/alias, portanto não autentica no Gmail. A
App Password é criada na conta `hey@hiago.sh` com 2-Step Verification ativa e
fica somente no dashboard/secret store. Não a registre em Markdown, git,
comandos, logs ou conversas.

Para usar o endereço do grupo como remetente, ele precisa estar autorizado em
Gmail/Google Workspace como **Send mail as** para `hey@hiago.sh`. O teste
recebido confirmou `From: Newsletter hiago.sh <newsletter@hiago.sh>`, TLS e
assinatura de `hiago.sh`.

Para uma comunicação pessoal, escolha explicitamente `hey@hiago.sh` no campo
**From** da campanha. Para a newsletter, mantenha o remetente do grupo. O
campo `from_email` pertence à campanha; ele não é uma chave da configuração
SMTP.

> O e-mail de **Test connection** inclui `Powered by listmonk` por ser um
> template de sistema. O template das campanhas não inclui essa marca. Só
> altere os templates estáticos do listmonk se também quiser rebrandeiar
> confirmações de opt-in e outros e-mails automáticos.

## Gerenciar via Hermes

Peça ao Hermes em linguagem natural. Exemplos:

> "Cria uma lista chamada Newsletter tipo public com optin double"

> "Adiciona o email user@example.com na lista Newsletter"

> "Cria uma campanha de teste com assunto 'Hello' pra lista Newsletter, mas não envia ainda"

> "Lista todos os subscribers"

O Hermes usa a skill `barbarossa-listmonk` para saber os endpoints e a
autenticação.

### O que o Hermes pode fazer (permissões do user `hermes`)

- **Listas**: criar, listar, atualizar, deletar
- **Subscribers**: criar, listar, importar, gerenciar listas
- **Campanhas**: criar, listar, ver analytics, gerenciar, **enviar**
- **Templates**: listar e criar; edição/promoção do template padrão requer acesso administrativo
- **Media**: listar, gerenciar
- **Bounces**: listar, gerenciar

### Enviar campanha (requer atenção)

Campanhas NÃO são enviadas ao criar. O Hermes deve:

1. Criar a campanha com `status: draft`
2. Colocar em `scheduled` com um `run_at` futuro

Nunca use `run_at` no passado. O envio é uma ação visível externamente —
sempre confirme com o operador antes.

### Teste de campanha sem broadcast

O endpoint `POST /api/campaigns/{id}/test` envia apenas aos endereços passados
em `subscribers`; ele não muda a campanha de `draft` nem entrega à lista
inteira. Na v6.2.0 ele exige o **payload completo da campanha**, além de
`subscribers`, e não aceita somente a lista de destinatários. Use-o apenas
para endereços de teste aprovados pelo operador.

A campanha de teste atual é a ID `2`, associada somente à lista ID `3`; ela
foi testada com os dois inscritos de teste do operador e continua com
`status: draft`, `sent: 0`.

Foram enviados três exemplos somente aos dois inscritos de teste aprovados:

| Template | Estilo | Estado |
|---|---|---|
| ID `6` | Ícone do portfólio acima do nome | enviado para teste |
| ID `7` | Ícone ao lado de `hiago.sh`, cabeçalho compacto | enviado para teste |
| ID `8` | Ícone como selo editorial centralizado | enviado para teste |

Todos usam `https://hiago.sh/icon.svg`, mantêm `{{ UnsubscribeURL }}` e
`{{ TrackView }}`, e não usam `{{ MessageURL }}` nem `Powered by listmonk`.
O Hermes recebeu HTTP 403 ao tentar fazer `PUT /api/templates/5`; não repetir
tentativas com esse usuário. O operador promoveu a variante compacta (ID `7`)
via dashboard administrativo para o template padrão ID `5`.

## Template editorial e escolha da variante

O template ID `5`, `Carta semanal — hiago.sh`, é o padrão atual e usa o layout
compacto: favicon `https://hiago.sh/icon.svg` ao lado de `hiago.sh`, apenas
`Cancelar inscrição` no rodapé e sem `Ver no navegador`. As outras variantes
de referência são IDs `6` e `8`. O usuário `hermes` recebeu 403 ao tentar
editar o ID 5; mudanças de template padrão exigem o dashboard administrativo.

Para uma edição nova, use `template_id: 5`, escreva somente o conteúdo
editorial em `body` e uma versão textual em `altbody`. Não use
`Powered by listmonk` no conteúdo.

## Token da API

O token do user `hermes` foi gerado e guardado fora do git (arquivo local
`/tmp/listmonk-hermes-token.txt` e hash no banco do listmonk).

Para usar manualmente via curl:

```bash
TOKEN="<token do arquivo>"
curl -u "hermes:$TOKEN" http://localhost:9000/api/lists
```

Se a auth falhar com `invalid API credentials` após criar/alterar user:

```bash
# O listmonk cacheia API users em memória. Reinicie o app:
ssh ovh 'cd /opt/stacks/listmonk && sudo docker compose restart app'
```

## Consultas úteis na API

| Endpoint | Descrição |
|---|---|
| `GET /api/lists` | Lista todas as listas |
| `POST /api/lists` | Cria lista |
| `GET /api/subscribers` | Lista subscribers |
| `POST /api/subscribers` | Cria subscriber |
| `PUT /api/subscribers/lists` | Altera membership |
| `GET /api/campaigns` | Lista campanhas |
| `POST /api/campaigns` | Cria campanha (draft) |
| `PUT /api/campaigns/{id}/status` | Muda status (scheduled/sending) |
| `POST /api/campaigns/{id}/test` | Testa para destinatários explícitos; requer campanha completa + `subscribers` |
| `GET /api/templates` | Lista templates |
| `POST /api/templates` | Cria variante de template (permitido ao user `hermes`) |
| `PUT /api/templates/{id}` | Pode retornar 403 para editar/promover template; usar dashboard admin |

## Documentação oficial

- [listmonk docs](https://listmonk.app/docs/)
- [API introduction](https://listmonk.app/docs/apis/apis/)
- [API lists](https://listmonk.app/docs/apis/lists/)
- [API subscribers](https://listmonk.app/docs/apis/subscribers/)
- [API campaigns](https://listmonk.app/docs/apis/campaigns/)
- [User roles e permissões](https://listmonk.app/docs/roles-and-permissions/)
