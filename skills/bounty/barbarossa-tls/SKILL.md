---
name: barbarossa-tls
description: Reach Cloudflare-gated bounty targets that refuse plain HTTP clients.
---

# Cloudflare-gated targets

Some program assets answer 403 (or a JS challenge page) to every plain HTTP client, including `curl`
with perfect browser headers and a valid session. The gate is the **TLS handshake fingerprint**
(JA3/JA4), not the User-Agent, not the cookies, not `Sec-Fetch-*`.

Do not conclude "the site blocks us" and move on. Measure it:

1. `curl` with the session and browser-like headers → note status and body size.
2. Same request via `scripts/bounty/tls_client.py` (curl_cffi impersonating Chrome) → note status.

If the second one succeeds, the asset is TLS-gated and every engagement on it needs this client.

## Use

```sh
# check reachability, read-only, one line per URL
python3 scripts/bounty/tls_client.py <session-file> <handle> https://target.example/

# from code
from tls_client import TlsClient
c = TlsClient(session_file=..., handle="uphiago")
r = c.fetch("https://target.example/")
c.save(r, "artifacts/page.html")
```

The client enforces the engagement rules by construction: GET-only unless `allow_write=True`, a
1 request/second throttle, `X-HackerOne-Research: <handle>` on every request, cookie values never
printed (logs carry names and counts), and evidence dumpable to disk.

## Rules that travel with this tool

- **Read-only unless authorized.** The default is GET. A mutation is a deliberate `allow_write=True`.
- **Own accounts only.** Program policies routinely permit only accounts you own. Authorization
  testing that needs a second identity is *blocked on a second owned account*, never attempted with
  hostile object ids against real users.
- **Never commit the session.** Keep it mode 600 outside the repository; commit the path convention,
  never a value. `scan-secrets.sh` must stay clean.
- **Rate.** When the policy states no numeric limit, keep ~1 req/s and one request per host per pass.

## Pitfalls

- **A JS challenge is not the same as a block.** An obfuscated page that loads one external script is
  the anti-bot interstitial. A TLS-impersonating client usually gets the real page; a real browser
  always does. Reading the interstitial is fine; *solving* it to defeat bot management is out of
  scope for most programs.
- **Client bundles often sit on a CDN host outside the scope list.** The application's API paths live
  in those bundles. Fetching them by direct URL is a request to an out-of-scope host. Load the page in
  a browser instead — the page pulls its own assets, which is normal client behaviour, not a probe.
- **Lightweight browser backends cannot run production JS.** If flow mapping needs real JavaScript,
  install Chromium and point the harness at it (`BH_CHROME_PATH`). A minimal engine will time out on
  heavy applications and look like a site failure.
- **A session is bound to more than its cookies.** Anti-bot tokens (`__cf_bm`, fingerprint cookies)
  are short-lived and sometimes IP-bound. If a copied session stops working, suspect token expiry
  before suspecting the account.
