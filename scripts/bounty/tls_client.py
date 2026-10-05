#!/usr/bin/env python3
"""TLS-impersonating HTTP client for authorized bounty work on Cloudflare-fronted targets.

Why this exists: some program assets sit behind Cloudflare bot management that gates on the **TLS
(JA3/JA4) fingerprint**, not on headers. Measured on a live in-scope asset: the same request with the
same cookies returned 403 to plain `curl` (even with browser-like headers) and 200 to a client
impersonating Chrome's handshake. Without this, those assets are unreachable and the engagement
stalls on a false "the site blocks us".

Design rules baked in, because they are engagement rules:
  - **Read-only by default.** `fetch()` is GET only. Any other method requires `allow_write=True`,
    which the caller must set deliberately. A harvest loop cannot accidentally mutate state.
  - **Rate limited.** Default 1 request/second, enforced by the client, not by the caller.
  - **Authorization header always attached.** `X-HackerOne-Research: <handle>` on every request.
  - **Secrets never printed.** Session values load from a file path; log lines carry cookie *names*
    and counts, never values.
  - **Evidence on disk.** Every response can be dumped to a directory for the record.

Usage:
    from tls_client import TlsClient
    c = TlsClient(session_file=os.environ["SESSION_FILE"], handle="your-h1-handle",
                  cookie_prefix="PROGRAM")   # matches PROGRAM_COOKIE in the session file
    r = c.fetch("https://www.target.com/")          # GET, rate limited, header attached
    c.fetch(url, method="POST")                    # raises unless allow_write=True
    c.save(r, "/path/artifact.html")

Dependency: `curl_cffi` (pip install curl_cffi). It carries its own TLS stack; no browser needed for
plain HTTP work. Use a real browser when you must execute the page's JS.
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path
from typing import Mapping

try:
    from curl_cffi import requests
except ImportError:  # pragma: no cover
    sys.exit("curl_cffi is required: pip install curl_cffi")

# Cookie env keys are shaped target_COOKIE_<NAME>; the combined header is target_COOKIE.
_COMBINED = re.compile(r"^(?P<prefix>[A-Z0-9]+)_COOKIE='(?P<value>.*)'$", re.M | re.S)
_DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class TlsClient:
    """A rate-limited, read-only-by-default, TLS-impersonating client."""

    def __init__(
        self,
        session_file: str,
        handle: str,
        cookie_prefix: str,
        impersonate: str = "chrome",
        rate: float = 1.0,
        timeout: int = 40,
        cookie_domain: str = "",
        user_agent: str | None = None,
    ) -> None:
        self.handle = handle
        self.impersonate = impersonate
        self.rate = max(rate, 0.0)
        self.timeout = timeout
        self.cookie_domain = cookie_domain
        self._last = 0.0
        self.cookies = self._load_cookies(session_file, cookie_prefix)
        self.headers: dict[str, str] = {"X-HackerOne-Research": handle, **_DEFAULT_HEADERS}
        if user_agent:
            self.headers["User-Agent"] = user_agent
        self.session = requests.Session(impersonate=impersonate)
        for name, value in self.cookies.items():
            self.session.cookies.set(name, value, domain=cookie_domain or None)

    # -- secrets ---------------------------------------------------------------------------------
    @staticmethod
    def _load_cookies(session_file: str, prefix: str) -> dict[str, str]:
        path = Path(session_file)
        if not path.is_file():
            sys.exit(f"session file not found: {session_file}")
        raw = path.read_text()
        for m in _COMBINED.finditer(raw):
            if m.group("prefix") == prefix:
                break
        else:
            sys.exit(f"no {prefix}_COOKIE found in {session_file}")
        cookies: dict[str, str] = {}
        for part in m.group("value").split("; "):
            if "=" in part:
                k, v = part.split("=", 1)
                cookies[k.strip()] = v
        return cookies

    def described(self) -> str:
        """A safe summary for logs and records: names and count, never values."""
        return f"{len(self.cookies)} cookies ({', '.join(sorted(self.cookies))})"

    # -- transport -------------------------------------------------------------------------------
    def _throttle(self) -> None:
        wait = self.rate - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()

    def fetch(
        self,
        url: str,
        method: str = "GET",
        allow_write: bool = False,
        extra_headers: Mapping[str, str] | None = None,
        **kwargs,
    ):
        """One request. GET by default; anything else needs allow_write=True."""
        method = method.upper()
        if method not in _SAFE_METHODS and not allow_write:
            raise PermissionError(
                f"{method} refused: engagement rule is read-only. "
                "Pass allow_write=True only for changes you have authorization to make."
            )
        headers = dict(self.headers)
        if extra_headers:
            headers.update(extra_headers)
        self._throttle()
        return self.session.request(
            method, url, headers=headers, impersonate=self.impersonate,
            timeout=self.timeout, allow_redirects=True, **kwargs,
        )

    # -- evidence --------------------------------------------------------------------------------
    @staticmethod
    def save(response, path: str) -> str:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(response.content)
        return str(p)

    @staticmethod
    def summarize(response) -> dict:
        """The redacted shape of a response, for records."""
        return {
            "status": response.status_code,
            "bytes": len(response.content),
            "final_url": str(response.url),
            "server": response.headers.get("server"),
            "cf_ray": response.headers.get("cf-ray"),
            "content_type": response.headers.get("content-type"),
        }


def main() -> int:
    """CLI: tls_client.py <session-file> <handle> <url>... -- read-only, one line per URL."""
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    session_file, handle, *urls = sys.argv[1:]
    client = TlsClient(session_file=session_file, handle=handle)
    print(f"# session: {client.described()}")
    for url in urls:
        try:
            r = client.fetch(url)
            s = client.summarize(r)
            print(f"{s['status']:>4} {s['bytes']:>9} B  {s['final_url'][:100]}")
        except Exception as exc:  # noqa: BLE001
            print(f"ERR  {url}: {str(exc)[:120]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
