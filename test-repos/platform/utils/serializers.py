import json
import time
from typing import Any, Optional
from core.logging import warn


def to_json(data: Any, pretty: bool = False) -> str:
    indent = 2 if pretty else None
    try:
        return json.dumps(data, default=_default_serializer, indent=indent)
    except (TypeError, ValueError) as e:
        warn("serialization_error", error=str(e))
        raise


def from_json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        warn("deserialization_error", error=str(e))
        raise


def _default_serializer(obj: Any) -> Any:
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def serialize_user(user) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "created_at": user.created_at,
    }


def serialize_user_full(user) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "roles": user.roles,
        "created_at": user.created_at,
        "post_count": user.post_count(),
    }


def serialize_post(post) -> dict:
    return {
        "id": post.id,
        "author_id": post.author_id,
        "title": post.title,
        "body": post.body,
        "tags": post.tags,
        "created_at": post.created_at,
    }


def serialize_post_summary(post) -> dict:
    return {
        "id": post.id,
        "author_id": post.author_id,
        "title": post.title,
        "tags": post.tags,
        "created_at": post.created_at,
    }


def serialize_comment(comment: dict) -> dict:
    return {
        "id": comment.get("id"),
        "post_id": comment.get("post_id"),
        "author_id": comment.get("author_id"),
        "body": comment.get("body"),
        "created_at": comment.get("created_at"),
    }


def serialize_list(items: list, serializer) -> list:
    return [serializer(item) for item in items]


def paginated_response(items: list, serializer, total: int, limit: int, offset: int) -> dict:
    return {
        "items": serialize_list(items, serializer),
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total,
    }


def error_response(code: str, message: str, field: Optional[str] = None) -> dict:
    result: dict = {"error": code, "message": message}
    if field:
        result["field"] = field
    return result


def success_response(data: Any = None, message: str = "ok") -> dict:
    result: dict = {"status": "ok", "message": message}
    if data is not None:
        result["data"] = data
    return result


def wrap_envelope(data: Any, meta: Optional[dict] = None) -> dict:
    envelope: dict = {"data": data, "timestamp": time.time()}
    if meta:
        envelope["meta"] = meta
    return envelope


def flatten_errors(errors: list[dict]) -> list[str]:
    return [f"{e.get('field', 'unknown')}: {e.get('message', '')}" for e in errors]


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("1", "true", "yes", "on")
    return bool(value)


def strip_null_values(data: dict) -> dict:
    return {k: v for k, v in data.items() if v is not None}
