from core.csrf import create_csrf_token, csrf_token_is_valid, csrf_tokens_match
from core.security import create_pkce_challenge, generate_pkce_verifier


def test_pkce_challenge_uses_s256() -> None:
    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"

    assert create_pkce_challenge(verifier) == (
        "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    )


def test_generated_pkce_verifier_has_valid_length() -> None:
    verifier = generate_pkce_verifier()

    assert 43 <= len(verifier) <= 128


def test_csrf_tokens_match_requires_cookie_and_header() -> None:
    secret = "csrf-test-secret"
    token = create_csrf_token(secret)

    assert csrf_tokens_match(token, token, secret) is True
    assert csrf_tokens_match(token, create_csrf_token(secret), secret) is False
    assert csrf_tokens_match(token, None, secret) is False
    assert csrf_tokens_match(None, token, secret) is False


def test_csrf_token_rejects_malformed_tampered_and_wrong_secret() -> None:
    secret = "csrf-test-secret"
    token = create_csrf_token(secret)
    version, nonce, signature = token.split(".")

    assert token.startswith("v1.")
    assert csrf_token_is_valid(token, secret) is True
    assert csrf_token_is_valid("unsigned-token", secret) is False
    changed_nonce = nonce[:-1] + ("A" if nonce[-1] != "A" else "B")
    changed_signature = signature[:-1] + (
        "A" if signature[-1] != "A" else "B"
    )
    assert csrf_token_is_valid(
        f"{version}.{changed_nonce}.{signature}", secret
    ) is False
    assert csrf_token_is_valid(
        f"{version}.{nonce}.{changed_signature}", secret
    ) is False
    assert csrf_token_is_valid(token, "different-secret") is False
