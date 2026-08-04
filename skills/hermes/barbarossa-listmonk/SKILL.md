---
name: barbarossa-listmonk
description: Manage the self-hosted listmonk mailing list server through the Recon network lane.
---

# Barbarossa Listmonk

Manage lists, subscribers, and campaigns on the listmonk instance running on
the same host as Barbarossa.

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

# Delete by id
curl -u "hermes:TOKEN" -X DELETE http://172.19.0.4:9000/api/lists/3
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
  -d '{"name":"Campaign","subject":"Hello","lists":[1],"from_email":"no-reply@example.com","type":"regular","content_type":"html","body":"<p>Hello</p>","status":"draft"}' \
  http://172.19.0.4:9000/api/campaigns

# Schedule / send a campaign: set status to scheduled with a run_at time
curl -u "hermes:TOKEN" -X PUT -H "Content-Type: application/json" \
  -d '{"status":"scheduled","run_at":"2026-08-04T18:00:00Z"}' \
  http://172.19.0.4:9000/api/campaigns/5/status
```

Campaigns are NOT sent on creation. They must be put in `scheduled` status
with a future `run_at`, or sent from the dashboard. Never set a past
`run_at`.

### Templates

```bash
curl -u "hermes:TOKEN" "http://172.19.0.4:9000/api/templates?per_page=all"
```

## Security

- Never write the token into a command that is logged to stdout of a shared
  job. Use `network_inspect` and keep the token in the job input file, or
  read it from the environment where the operator provided it.
- The API user has management permissions over lists, subscribers,
  campaigns, templates, media, and bounces. Treat it as privileged.
- Do not send campaigns without explicit operator instruction. Sending is a
  state-changing, externally visible action.
