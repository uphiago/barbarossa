import re

AUTH_HEADER_RE = re.compile(
    r"(?im)^(authorization:\s*)(?:bearer|basic)\s+\S+"
)
TOKEN_RE = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{16,})\b"
)
PEM_RE = re.compile(
    r"-----BEGIN [^-]*PRIVATE KEY-----.*?"
    r"-----END [^-]*PRIVATE KEY-----",
    re.DOTALL,
)


class Redactor:
    def __init__(
        self,
        secrets: list[str],
        max_bytes: int = 200_000,
    ) -> None:
        self._secrets = sorted(
            (secret for secret in secrets if secret),
            key=len,
            reverse=True,
        )
        self._max_bytes = max_bytes

    def clean(self, value: str) -> str:
        cleaned = AUTH_HEADER_RE.sub(r"\1[REDACTED]", value)
        cleaned = TOKEN_RE.sub("[REDACTED]", cleaned)
        cleaned = PEM_RE.sub("[REDACTED PRIVATE KEY]", cleaned)
        for secret in self._secrets:
            cleaned = cleaned.replace(secret, "[REDACTED]")
        return cleaned.encode()[: self._max_bytes].decode(errors="replace")
