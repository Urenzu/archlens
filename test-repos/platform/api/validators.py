import re
from typing import Any, Optional
from core.errors import ValidationError, raise_validation


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SLUG_RE = re.compile(r"^[a-z0-9-]+$")


def validate_email(value: Any) -> str:
    if not isinstance(value, str) or not EMAIL_RE.match(value):
        raise_validation("email", "must be a valid email address")
    return value.lower().strip()


def validate_password(value: Any) -> str:
    if not isinstance(value, str):
        raise_validation("password", "must be a string")
    if len(value) < 8:
        raise_validation("password", "must be at least 8 characters")
    if len(value) > 128:
        raise_validation("password", "must be at most 128 characters")
    if not re.search(r"[A-Z]", value):
        raise_validation("password", "must contain at least one uppercase letter")
    if not re.search(r"\d", value):
        raise_validation("password", "must contain at least one digit")
    return value


def validate_string(field: str, value: Any, min_len: int = 1, max_len: int = 1000) -> str:
    if not isinstance(value, str):
        raise_validation(field, "must be a string")
    stripped = value.strip()
    if len(stripped) < min_len:
        raise_validation(field, f"must be at least {min_len} characters")
    if len(stripped) > max_len:
        raise_validation(field, f"must be at most {max_len} characters")
    return stripped


def validate_int(field: str, value: Any, min_val: int = 0, max_val: int = 10000) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise_validation(field, "must be an integer")
    if n < min_val or n > max_val:
        raise_validation(field, f"must be between {min_val} and {max_val}")
    return n


def validate_list(field: str, value: Any, max_items: int = 50) -> list:
    if not isinstance(value, list):
        raise_validation(field, "must be an array")
    if len(value) > max_items:
        raise_validation(field, f"must have at most {max_items} items")
    return value


def validate_slug(field: str, value: Any) -> str:
    s = validate_string(field, value, 1, 100)
    if not SLUG_RE.match(s):
        raise_validation(field, "must contain only lowercase letters, numbers, and hyphens")
    return s


def parse_pagination(params: dict) -> tuple[int, int]:
    limit = validate_int("limit", params.get("limit", 20), 1, 100)
    offset = validate_int("offset", params.get("offset", 0), 0, 100000)
    return limit, offset


def validate_create_user(body: dict) -> dict:
    return {
        "email": validate_email(body.get("email")),
        "password": validate_password(body.get("password", "")),
        "roles": validate_list("roles", body.get("roles", ["viewer"]), 10),
    }


def validate_create_post(body: dict) -> dict:
    return {
        "title": validate_string("title", body.get("title"), 1, 200),
        "body": validate_string("body", body.get("body"), 1, 100_000),
        "tags": validate_list("tags", body.get("tags", []), 20),
    }


def validate_search_params(params: dict) -> dict:
    q = validate_string("q", params.get("q", ""), 1, 200)
    limit, offset = parse_pagination(params)
    return {"q": q, "limit": limit, "offset": offset}


def sanitize_html(value: str) -> str:
    # Very basic — strip obvious script tags
    value = re.sub(r"<script[^>]*>.*?</script>", "", value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"on\w+\s*=\s*[\"'][^\"']*[\"']", "", value, flags=re.IGNORECASE)
    return value
