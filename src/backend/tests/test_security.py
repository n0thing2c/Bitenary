from core.csrf import csrf_tokens_match
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
    assert csrf_tokens_match("token", "token") is True
    assert csrf_tokens_match("token", "other") is False
    assert csrf_tokens_match("token", None) is False
    assert csrf_tokens_match(None, "token") is False
