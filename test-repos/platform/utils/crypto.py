import hashlib
import hmac
import os
import base64
import secrets
from typing import Optional
from core.logging import debug, warn


HASH_ALGORITHM = "sha256"
PBKDF2_ITERATIONS = 260_000
SALT_BYTES = 32
TOKEN_BYTES = 32


def generate_salt() -> str:
    return base64.b64encode(os.urandom(SALT_BYTES)).decode("utf-8")


def hash_password(password: str, salt: Optional[str] = None) -> str:
    if salt is None:
        salt = generate_salt()
    salt_bytes = base64.b64decode(salt.encode("utf-8"))
    dk = hashlib.pbkdf2_hmac(HASH_ALGORITHM, password.encode("utf-8"), salt_bytes, PBKDF2_ITERATIONS)
    hashed = base64.b64encode(dk).decode("utf-8")
    return f"{salt}${hashed}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, _ = stored_hash.split("$", 1)
    except ValueError:
        warn("hash_format_invalid")
        return False
    candidate = hash_password(password, salt)
    return hmac.compare_digest(candidate, stored_hash)


def generate_token(nbytes: int = TOKEN_BYTES) -> str:
    return secrets.token_urlsafe(nbytes)


def generate_api_key() -> str:
    prefix = "ak_live_"
    return prefix + secrets.token_urlsafe(40)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def sign_payload(payload: str, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256)
    return sig.hexdigest()


def verify_signature(payload: str, signature: str, secret: str) -> bool:
    expected = sign_payload(payload, secret)
    return hmac.compare_digest(expected, signature)


def encode_base64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8")


def decode_base64(data: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(data.encode("utf-8") + b"==")
    except Exception as e:
        warn("base64_decode_error", error=str(e))
        raise ValueError("invalid base64") from e


def constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def derive_key(master_key: str, context: str, length: int = 32) -> bytes:
    return hashlib.pbkdf2_hmac(
        HASH_ALGORITHM,
        master_key.encode("utf-8"),
        context.encode("utf-8"),
        1000,
        dklen=length,
    )


def mask_sensitive(value: str, show_chars: int = 4) -> str:
    if len(value) <= show_chars:
        return "*" * len(value)
    return value[:show_chars] + "*" * (len(value) - show_chars)
