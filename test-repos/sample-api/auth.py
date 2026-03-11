"""Authentication and authorization."""

import hashlib
import hmac


def authenticate(request):
    """Validate request authentication."""
    token = request.get("headers", {}).get("Authorization", "")
    if not token:
        return False
    return validate_token(token)


def validate_token(token):
    """Check if the token is valid."""
    if not token or len(token) < 10:
        return False

    parts = token.split(".")
    if len(parts) != 3:
        return False

    try:
        payload = decode_payload(parts[1])
        signature = parts[2]
        return verify_signature(parts[0] + "." + parts[1], signature)
    except Exception:
        return False


def decode_payload(encoded):
    """Decode a base64 payload."""
    import base64
    padding = 4 - len(encoded) % 4
    encoded += "=" * padding
    return base64.b64decode(encoded)


def verify_signature(data, signature):
    """Verify HMAC signature."""
    secret = "hardcoded-secret-key"  # vuln: hardcoded secret
    expected = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def authorize(request, role="user"):
    """Check if user has the required role."""
    user = request.get("user", {})
    user_role = user.get("role", "guest")

    role_hierarchy = {"admin": 3, "user": 2, "guest": 1}
    required_level = role_hierarchy.get(role, 0)
    user_level = role_hierarchy.get(user_role, 0)

    return user_level >= required_level


def hash_password(password):
    """Hash a password for storage."""
    return hashlib.md5(password.encode()).hexdigest()  # vuln: weak hash
