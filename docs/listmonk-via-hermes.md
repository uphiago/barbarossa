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

## Acesso ao dashboard

Com o túnel ativo:

```bash
ssh ovh          # túnel com LocalForward 9000
# no navegador:
# http://localhost:9000
```

Login no dashboard: usuário **hiagod** (criado no primeiro acesso).

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
- **Templates**: listar, gerenciar
- **Media**: listar, gerenciar
- **Bounces**: listar, gerenciar

### Enviar campanha (requer atenção)

Campanhas NÃO são enviadas ao criar. O Hermes deve:

1. Criar a campanha com `status: draft`
2. Colocar em `scheduled` com um `run_at` futuro

Nunca use `run_at` no passado. O envio é uma ação visível externamente —
sempre confirme com o operador antes.

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
| `GET /api/templates` | Lista templates |

## Documentação oficial

- [listmonk docs](https://listmonk.app/docs/)
- [API introduction](https://listmonk.app/docs/apis/apis/)
- [API lists](https://listmonk.app/docs/apis/lists/)
- [API subscribers](https://listmonk.app/docs/apis/subscribers/)
- [API campaigns](https://listmonk.app/docs/apis/campaigns/)
- [User roles e permissões](https://listmonk.app/docs/roles-and-permissions/)
