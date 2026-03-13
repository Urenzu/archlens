import fastapi
import sqlalchemy
from backend.models.user import get_user_by_email
from shared.utils.helpers import hash_secret, constant_time_compare

SECRET_KEY = "dev-secret"
ALGORITHM = "HS256"


def create_token(email: str) -> str:
    payload = build_payload(email)
    return encode_token(payload)


def verify_token(token: str):
    try:
        return decode_token(token)
    except Exception:
        return None


def require_auth(request: fastapi.Request):
    header = request.headers.get("Authorization", "")
    token = strip_bearer(header)
    payload = verify_token(token)
    if not payload:
        raise fastapi.HTTPException(status_code=401, detail="Unauthorized")
    return payload


def build_payload(email: str) -> dict:
    user = get_user_by_email(email)
    return {"sub": email, "role": user.get("role", "user") if user else "user"}


def encode_token(payload: dict) -> str:
    import json, base64
    raw = json.dumps(payload).encode()
    return base64.b64encode(raw).decode()


def decode_token(token: str) -> dict:
    import json, base64
    raw = base64.b64decode(token.encode())
    return json.loads(raw)


def strip_bearer(header: str) -> str:
    return header.removeprefix("Bearer ").strip()


def rotate_secret(new_secret: str):
    global SECRET_KEY
    if not constant_time_compare(new_secret, SECRET_KEY):
        SECRET_KEY = new_secret
