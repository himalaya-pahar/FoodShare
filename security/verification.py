"""
Verification Token Security Module.
Provides cryptographically secure token generation and hashing for email verification.
Raw tokens are generated using secrets.token_urlsafe(32) and NEVER stored or logged.
Only the SHA-256 hash is persisted in the database.
"""
import hashlib
import secrets


def generate_verification_token() -> tuple[str, str]:
    """
    Generates a cryptographically secure random token and its SHA-256 hash.

    Returns:
        tuple[str, str]: (raw_token, token_hash)
        The raw_token should be sent to the user via email and NEVER logged or stored.
        The token_hash should be stored in the database.
    """
    # 32 bytes of randomness URL-safe encoded (yields ~43 characters, 256 bits of entropy)
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_verification_token(raw_token)
    return raw_token, token_hash


def hash_verification_token(raw_token: str) -> str:
    """
    Computes deterministic SHA-256 digest of the raw verification token.

    Args:
        raw_token: The raw random verification token string.

    Returns:
        Hexadecimal SHA-256 string.
    """
    if not raw_token:
        return ""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()
