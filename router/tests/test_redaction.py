from barbarossa_router.redaction import Redactor


def test_redacts_known_secret_and_authorization_header() -> None:
    redactor = Redactor(["super-secret-value"])
    text = "Authorization: Bearer abc123 super-secret-value"

    assert redactor.clean(text) == "Authorization: [REDACTED] [REDACTED]"


def test_redacts_common_token_shapes_and_private_keys() -> None:
    redactor = Redactor([])
    text = (
        "sk-1234567890abcdefghijklmnop "
        "ghp_1234567890abcdefghijklmnop "
        "-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----"
    )

    assert redactor.clean(text) == (
        "[REDACTED] [REDACTED] [REDACTED PRIVATE KEY]"
    )


def test_bounds_cleaned_output_by_bytes() -> None:
    redactor = Redactor([], max_bytes=4)

    assert redactor.clean("abcdef") == "abcd"
