from app.auth.security import (
    hash_password,
    hash_token,
    token_matches,
    validate_password,
    verify_password,
)


def test_argon2_password_hash_round_trip() -> None:
    password = "a long secure passphrase with enough length"
    hashed = hash_password(password)
    assert hashed != password
    assert hashed.startswith("$argon2")
    assert verify_password(password, hashed)
    assert not verify_password("wrong password", hashed)


def test_random_token_hash_is_only_valid_for_the_original_token() -> None:
    token = "high-entropy-token"
    digest = hash_token(token)
    assert token_matches(token, digest)
    assert not token_matches("different-token", digest)


def test_password_policy_allows_long_passphrases_and_rejects_short_values() -> None:
    validate_password("this is a long passphrase")
    try:
        validate_password("short")
    except ValueError as exc:
        assert "at least" in str(exc)
    else:
        raise AssertionError("short password was accepted")
