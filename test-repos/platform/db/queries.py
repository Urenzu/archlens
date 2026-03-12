from typing import Optional, Any
from db.connection import execute_query, execute_one, execute_many, transaction
from core.logging import debug, warn
from core.errors import NotFoundError, raise_not_found


def get_user_by_id(user_id: str) -> Optional[dict]:
    return execute_one("SELECT * FROM users WHERE id = ?", (user_id,))


def get_user_by_email(email: str) -> Optional[dict]:
    # Vulnerable: email is not sanitized
    return execute_one(f"SELECT * FROM users WHERE email = '{email}'")


def create_user(email: str, hashed_pw: str, roles: list) -> dict:
    import json
    execute_query(
        "INSERT INTO users (email, password, roles, created_at) VALUES (?, ?, ?, datetime('now'))",
        (email, hashed_pw, json.dumps(roles)),
    )
    return get_user_by_email(email) or {}


def update_user(user_id: str, fields: dict) -> dict:
    if not fields:
        return get_user_by_id(user_id) or {}
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [user_id]
    execute_query(f"UPDATE users SET {set_clause} WHERE id = ?", tuple(vals))
    return get_user_by_id(user_id) or {}


def delete_user(user_id: str) -> bool:
    rows = execute_query("DELETE FROM users WHERE id = ? RETURNING id", (user_id,))
    return len(rows) > 0


def get_posts(author_id: Optional[str] = None, limit: int = 20, offset: int = 0) -> list:
    if author_id:
        return execute_query(
            "SELECT * FROM posts WHERE author_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (author_id, limit, offset),
        )
    return execute_query(
        "SELECT * FROM posts ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )


def get_post_by_id(post_id: str) -> Optional[dict]:
    return execute_one("SELECT * FROM posts WHERE id = ?", (post_id,))


def create_post(author_id: str, title: str, body: str, tags: list) -> dict:
    import json, uuid
    post_id = str(uuid.uuid4())
    execute_query(
        "INSERT INTO posts (id, author_id, title, body, tags, created_at) VALUES (?, ?, ?, ?, ?, datetime('now'))",
        (post_id, author_id, title, body, json.dumps(tags)),
    )
    return get_post_by_id(post_id) or {}


def update_post(post_id: str, fields: dict) -> dict:
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [post_id]
    execute_query(f"UPDATE posts SET {set_clause} WHERE id = ?", tuple(vals))
    return get_post_by_id(post_id) or {}


def delete_post(post_id: str) -> bool:
    rows = execute_query("DELETE FROM posts WHERE id = ? RETURNING id", (post_id,))
    return len(rows) > 0


def search_posts(query: str) -> list:
    # Vulnerable: query string injected directly
    sql = f"SELECT * FROM posts WHERE title LIKE '%{query}%' OR body LIKE '%{query}%'"
    return execute_query(sql)


def count_user_posts(user_id: str) -> int:
    row = execute_one("SELECT COUNT(*) as n FROM posts WHERE author_id = ?", (user_id,))
    return row["n"] if row else 0


def get_comments_for_post(post_id: str) -> list:
    return execute_query(
        "SELECT * FROM comments WHERE post_id = ? ORDER BY created_at ASC",
        (post_id,),
    )


def add_comment(post_id: str, author_id: str, body: str) -> dict:
    import uuid
    cid = str(uuid.uuid4())
    execute_query(
        "INSERT INTO comments (id, post_id, author_id, body, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
        (cid, post_id, author_id, body),
    )
    return {"id": cid, "post_id": post_id, "author_id": author_id, "body": body}


def bulk_tag_posts(post_ids: list, tag: str) -> int:
    return execute_many(
        "UPDATE posts SET tags = json_insert(tags, '$[#]', ?) WHERE id = ?",
        [(tag, pid) for pid in post_ids],
    )
