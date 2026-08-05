---
name: barbarossa-listmonk
description: Use when managing the self-hosted listmonk instance through the Hermes Recon lane, including newsletter lists, templates, campaign drafts, approved test sends, or operator-authorized broadcasts.
---

# Barbarossa Listmonk

Manage lists, subscribers, templates, and campaigns on the listmonk instance
running on the same host as Barbarossa. Keep broadcasts opt-in and explicit.

## Endpoint

The listmonk app is reachable from Recon only. Do not use Forge or direct
Hermes network calls.

```text
http://172.19.0.4:9000
```

The address may change if the container is recreated. Re-resolve it with:

```bash
docker inspect listmonk_app --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{$v.IPAddress}}{{end}}'
```

## Authentication

Use the `hermes` API user. The token is a SHA-256 hex digest stored in the
listmonk database; the operator keeps the plaintext token outside this
repository.

```bash
# BasicAuth
curl -u "hermes:TOKEN" http://172.19.0.4:9000/api/lists

# Authorization header
curl -H "Authorization: token hermes:TOKEN" http://172.19.0.4:9000/api/lists
```

A `403 invalid API credentials` after adding or changing a user means the
listmonk app has not reloaded its in-memory API user cache. Restart the app:

```bash
cd /opt/stacks/listmonk && sudo docker compose restart app
```

The `hermes` role intentionally does not manage **Settings**. SMTP is
database-backed and configured only in the dashboard; never request, expose,
or store its App Password.

## Instance facts

| Item | Current value |
|---|---|
| List | ID `3`, `Newsletter`, `public`, `double` opt-in |
| Current default template | ID `5`, `Carta semanal — hiago.sh`; compact portfolio-icon layout |
| Corrected test templates | IDs `6`, `7`, `8`; portfolio icon and unsubscribe-only footer |
| Example campaign | ID `2`, draft only; it has not been broadcast |
| SMTP auth account | `hey@hiago.sh` (do not handle its password) |
| Newsletter sender | `Newsletter <newsletter@hiago.sh>` |

`newsletter@hiago.sh` is a group/alias, not the SMTP login. The verified SMTP
configuration is Gmail on port 465 with `LOGIN` and `TLS`; `hey@hiago.sh`
authenticates and is authorized to send as the newsletter group. For a
personal campaign, set `from_email` to `hey@hiago.sh` explicitly.

## Tools

Use `network_inspect` for all listmonk calls (it allows arbitrary curl
argv). `network_fetch` is GET-only without auth headers and does not fit
this API.

## Operation patterns

### Lists

```bash
# List all
curl -u "hermes:TOKEN" "http://172.19.0.4:9000/api/lists?per_page=all"

# Create
curl -u "hermes:TOKEN" -X POST \
  -H "Content-Type: application/json" \
  -d '{"name":"Newsletter","type":"public","optin":"double","tags":[],"description":""}' \
  http://172.19.0.4:9000/api/lists

# Delete only after the operator confirms the resolved ID and scope
curl -u "hermes:TOKEN" -X DELETE http://172.19.0.4:9000/api/lists/LIST_ID
```

### Subscribers

```bash
# List
curl -u "hermes:TOKEN" "http://172.19.0.4:9000/api/subscribers?per_page=all"

# Create and subscribe to a list
curl -u "hermes:TOKEN" -X POST \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","name":"User","status":"enabled","lists":[1],"attribs":{}}' \
  http://172.19.0.4:9000/api/subscribers

# Change list membership
curl -u "hermes:TOKEN" -X PUT -H "Content-Type: application/json" \
  -d '{"ids":[1,2],"action":"add","list_ids":[1]}' \
  http://172.19.0.4:9000/api/subscribers/lists
```

### Campaigns

```bash
# Create a campaign (status draft, does not send)
curl -u "hermes:TOKEN" -X POST \
  -H "Content-Type: application/json" \
  -d '{"name":"Campaign","subject":"Hello","lists":[3],"from_email":"Newsletter <newsletter@hiago.sh>","template_id":5,"type":"regular","content_type":"html","body":"<p>Hello</p>","altbody":"Hello","status":"draft"}' \
  http://172.19.0.4:9000/api/campaigns

# Schedule / send a campaign: set status to scheduled with a run_at time
curl -u "hermes:TOKEN" -X PUT -H "Content-Type: application/json" \
  -d '{"status":"scheduled","run_at":"<future RFC3339 timestamp>"}' \
  http://172.19.0.4:9000/api/campaigns/CAMPAIGN_ID/status
```

Campaigns are NOT sent on creation. They must be put in `scheduled` status
with a future `run_at`, or sent from the dashboard. Never set a past
`run_at`. Do not schedule or send without explicit operator authorization for
the exact campaign and audience.

### Test send

`POST /api/campaigns/{id}/test` is not a broadcast: it delivers only to the
explicit `subscribers` addresses and leaves the campaign as `draft`. In
listmonk v6.2.0, submit the complete campaign object plus `subscribers`; a
payload containing only `subscribers` returns HTTP 400. Send tests only to
operator-approved addresses, never all list members by default.

Fetch the campaign first, retain its writable fields (`name`, `subject`,
`lists`, `from_email`, `template_id`, `type`, `content_type`, `body`,
`altbody`, `status`, `messenger`), and add the explicit `subscribers` array.
Set `messenger: "email"`; omitting it returns HTTP 400 `Unknown messenger .`.
Do not reuse read-only response fields blindly. The same test flow sent three
examples to the two operator-approved test subscribers; do not repeat that
send unless explicitly requested.

### Templates

```bash
curl -u "hermes:TOKEN" "http://172.19.0.4:9000/api/templates?per_page=all"
```

The corrected variants are:

- ID `6`: portfolio icon above `hiago.sh`.
- ID `7`: compact icon beside `hiago.sh` (promoted to default template ID `5`).
- ID `8`: centered editorial badge.

Each uses `https://hiago.sh/icon.svg`, `{{ UnsubscribeURL }}` and
`{{ TrackView }}`, with no `{{ MessageURL }}` or listmonk branding. Use
`template_id: 5` for new campaigns. The API user can create templates but
received HTTP 403 on `PUT /api/templates/5`; change the default through the
admin dashboard.

## Security

- Never write the token into a command that is logged to stdout of a shared
  job. Use `network_inspect` and keep the token in the job input file, or
  read it from the environment where the operator provided it.
- The API user has management permissions over lists, subscribers,
  campaigns, templates, media, and bounces. Treat it as privileged.
- Do not send campaigns without explicit operator instruction. Sending is a
  state-changing, externally visible action.
- Keep the campaign body free of `Powered by listmonk`; that text belongs only
  to the built-in SMTP test/system mail template, not the editorial template.
