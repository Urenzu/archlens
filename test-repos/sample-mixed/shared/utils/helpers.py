import hashlib
import hmac
import uuid


def new_id() -> str:
    return str(uuid.uuid4())


def hash_secret(value: str) -> str:
    salt = generate_salt()
    return derive_key(value, salt)


def generate_salt() -> str:
    return uuid.uuid4().hex


def derive_key(value: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", value.encode(), salt.encode(), 100_000).hex()


def constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def paginate(items: list, page: int, limit: int) -> dict:
    start = (page - 1) * limit
    end = start + limit
    sliced = items[start:end]
    return build_page(sliced, page, limit, len(items))


def build_page(items: list, page: int, limit: int, total: int) -> dict:
    return {
        "items": items,
        "page": page,
        "limit": limit,
        "total": total,
        "pages": compute_pages(total, limit),
    }


def compute_pages(total: int, limit: int) -> int:
    if limit <= 0:
        return 0
    return (total + limit - 1) // limit


def format_response(data) -> dict:
    if isinstance(data, dict):
        return wrap_data(data)
    return wrap_data({"result": data})


def wrap_data(data: dict) -> dict:
    return {"ok": True, "data": data}
