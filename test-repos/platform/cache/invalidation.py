from typing import Optional
from cache.redis_client import delete, flush_pattern, exists, set_json, get_json
from core.logging import debug, info


def user_cache_key(user_id: str) -> str:
    return f"user:{user_id}"


def post_cache_key(post_id: str) -> str:
    return f"post:{post_id}"


def user_posts_key(user_id: str) -> str:
    return f"user:{user_id}:posts"


def post_comments_key(post_id: str) -> str:
    return f"post:{post_id}:comments"


def session_key(user_id: str) -> str:
    return f"session:{user_id}"


def invalidate_user(user_id: str) -> None:
    delete(user_cache_key(user_id))
    delete(user_posts_key(user_id))
    flush_pattern(f"user:{user_id}:*")
    info("cache_invalidated", entity="user", user_id=user_id)


def invalidate_post(post_id: str, author_id: Optional[str] = None) -> None:
    delete(post_cache_key(post_id))
    delete(post_comments_key(post_id))
    if author_id:
        delete(user_posts_key(author_id))
    info("cache_invalidated", entity="post", post_id=post_id)


def invalidate_session(user_id: str) -> None:
    delete(session_key(user_id))
    debug("session_invalidated", user_id=user_id)


def cache_user(user_id: str, data: dict, ttl: int = 300) -> None:
    set_json(user_cache_key(user_id), data, ttl)


def get_cached_user(user_id: str) -> Optional[dict]:
    return get_json(user_cache_key(user_id))


def cache_post(post_id: str, data: dict, ttl: int = 120) -> None:
    set_json(post_cache_key(post_id), data, ttl)


def get_cached_post(post_id: str) -> Optional[dict]:
    return get_json(post_cache_key(post_id))


def cache_user_posts(user_id: str, posts: list, ttl: int = 60) -> None:
    set_json(user_posts_key(user_id), posts, ttl)


def get_cached_user_posts(user_id: str) -> Optional[list]:
    return get_json(user_posts_key(user_id))


def warm_user_cache(user_id: str, fetch_fn) -> dict:
    cached = get_cached_user(user_id)
    if cached:
        return cached
    data = fetch_fn(user_id)
    if data:
        cache_user(user_id, data)
    return data or {}


def warm_post_cache(post_id: str, fetch_fn) -> Optional[dict]:
    cached = get_cached_post(post_id)
    if cached:
        return cached
    data = fetch_fn(post_id)
    if data:
        cache_post(post_id, data)
    return data
