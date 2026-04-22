import json
import time
import uuid
from typing import Optional, Any
from db.queries import (
    get_user_by_id, create_user, update_user, delete_user,
    get_post_by_id, create_post, update_post, delete_post,
    get_posts, get_comments_for_post, add_comment, count_user_posts,
)
from utils.crypto import hash_password, verify_password
from core.errors import NotFoundError, ValidationError, raise_not_found, raise_validation


class User:
    def __init__(self, data: dict):
        self.id = data.get("id", str(uuid.uuid4()))
        self.email = data.get("email", "")
        self.roles = json.loads(data.get("roles", '["viewer"]'))
        self.created_at = data.get("created_at", time.time())
        self._raw = data

    @classmethod
    def find(cls, user_id: str) -> "User":
        data = get_user_by_id(user_id)
        if not data:
            raise_not_found("User", user_id)
        return cls(data)

    @classmethod
    def create(cls, email: str, password: str, roles: list = None) -> "User":
        if not email or "@" not in email:
            raise_validation("email", "must be a valid email address")
        if len(password) < 8:
            raise_validation("password", "must be at least 8 characters")
        hashed = hash_password(password)
        data = create_user(email, hashed, roles or ["viewer"])
        return cls(data)

    def check_password(self, password: str) -> bool:
        return verify_password(password, self._raw.get("password", ""))

    def update(self, **fields) -> "User":
        allowed = {"email", "roles"}
        safe_fields = {k: v for k, v in fields.items() if k in allowed}
        if not safe_fields:
            return self
        data = update_user(self.id, safe_fields)
        return User(data)

    def delete(self) -> bool:
        return delete_user(self.id)

    def post_count(self) -> int:
        return count_user_posts(self.id)

    def to_dict(self, include_roles: bool = False) -> dict:
        result = {"id": self.id, "email": self.email, "created_at": self.created_at}
        if include_roles:
            result["roles"] = self.roles
        return result


class Post:
    def __init__(self, data: dict):
        self.id = data.get("id", str(uuid.uuid4()))
        self.author_id = data.get("author_id", "")
        self.title = data.get("title", "")
        self.body = data.get("body", "")
        self.tags = json.loads(data.get("tags", "[]"))
        self.created_at = data.get("created_at", time.time())

    @classmethod
    def find(cls, post_id: str) -> "Post":
        data = get_post_by_id(post_id)
        if not data:
            raise_not_found("Post", post_id)
        return cls(data)

    @classmethod
    def list(cls, author_id: str = None, limit: int = 20, offset: int = 0) -> list["Post"]:
        rows = get_posts(author_id, limit, offset)
        return [cls(r) for r in rows]

    @classmethod
    def create(cls, author_id: str, title: str, body: str, tags: list = None) -> "Post":
        if not title.strip():
            raise_validation("title", "cannot be empty")
        if len(body) > 100_000:
            raise_validation("body", "exceeds maximum length")
        data = create_post(author_id, title, body, tags or [])
        return cls(data)

    def update(self, **fields) -> "Post":
        allowed = {"title", "body", "tags"}
        safe = {k: v for k, v in fields.items() if k in allowed}
        data = update_post(self.id, safe)
        return Post(data)

    def delete(self) -> bool:
        return delete_post(self.id)

    def comments(self) -> list:
        return get_comments_for_post(self.id)

    def add_comment(self, author_id: str, body: str) -> dict:
        if not body.strip():
            raise_validation("body", "comment cannot be empty")
        return add_comment(self.id, author_id, body)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "author_id": self.author_id,
            "title": self.title,
            "body": self.body,
            "tags": self.tags,
            "created_at": self.created_at,
        }
