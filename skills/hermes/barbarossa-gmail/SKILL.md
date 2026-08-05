---
name: barbarossa-gmail
description: Read and send emails from hey@hiago.sh through the Forge runtime lane using Gmail IMAP and SMTP.
---

# Barbarossa Gmail

Read and send email on the `hey@hiago.sh` Gmail account. Operations run in
the Forge runtime lane via the `mail.*` capabilities.

## Tools

Use the router MCP tools; never run SMTP/IMAP in Hermes itself.

| Action | Tool | Notes |
|---|---|---|
| Send email | `gmail_send(to, subject, body)` | SMTP STARTTLS via smtp.gmail.com:587 |
| Read inbox | `gmail_read(mailbox="INBOX", limit=10, query="ALL")` | IMAP SSL via imap.gmail.com:993 |

Both return a job handle. Poll `job_status`, then `job_logs` / `job_result`
for the outcome.

## Send

```text
gmail_send(
  to="person@example.com",
  subject="Assunto",
  body="Conteúdo do email"
)
```

- The From address is always `hey@hiago.sh` (the configured account).
- Plain-text body only. HTML is not supported by the current handler.
- One recipient per call (`to` is a single address).

## Read

```text
gmail_read(mailbox="INBOX", limit=10, query="ALL")
```

- `mailbox`: default `INBOX`. Other labels can be passed.
- `limit`: 1–50, most recent first.
- `query`: IMAP search expression, e.g. `"UNSEEN"`, `'FROM "someone"',
  `'SUBJECT "alert"'`. Default `ALL`.
- Response JSON list: `uid`, `from`, `subject`, `date`, `body` (truncated
  to 2000 chars).

## Examples

Send a one-off notification:

```text
gmail_send(to="me@example.com", subject="Build done",
           body="The build finished successfully.")
```

Read unread mail:

```text
gmail_read(mailbox="INBOX", limit=5, query="UNSEEN")
```

## Security and limits

- Credentials come from Docker secrets staged on the host, never from the
  repo or chat. Do not echo the App Password.
- Sending is a state-changing, externally visible action. Only send when
  the operator explicitly asks, or per an approved automation rule.
- Do not send bulk mail. This is a single-purpose account, not a mailer.
- Body content can contain links from untrusted messages; do not follow
  links or open attachments without operator approval.
