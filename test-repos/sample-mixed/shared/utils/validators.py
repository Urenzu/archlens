import re

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_MIN = 8


def validate_email(email: str) -> bool:
    if not email or len(email) > 254:
        return False
    return bool(EMAIL_RE.match(email))


def validate_password(password: str) -> bool:
    if not password or len(password) < PASSWORD_MIN:
        return False
    return has_digit(password) and has_upper(password)


def validate_uuid(value: str) -> bool:
    parts = value.split("-")
    return len(parts) == 5 and all(is_hex(p) for p in parts)


def validate_url(url: str) -> bool:
    return url.startswith("https://") or url.startswith("http://")


def has_digit(s: str) -> bool:
    return any(c.isdigit() for c in s)


def has_upper(s: str) -> bool:
    return any(c.isupper() for c in s)


def is_hex(s: str) -> bool:
    try:
        int(s, 16)
        return True
    except ValueError:
        return False


def sanitize_string(value: str) -> str:
    stripped = value.strip()
    return escape_html(stripped)


def escape_html(value: str) -> str:
    return (value
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))
