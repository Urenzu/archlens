from typing import Optional
from api.router import get, post, put, patch, delete
from api.validators import (
    validate_create_user, validate_create_post, validate_search_params,
    validate_string, validate_int, parse_pagination, sanitize_html,
)
from db.models import User, Post
from db.queries import search_posts, bulk_tag_posts, get_user_by_email
from cache.invalidation import (
    get_cached_user, cache_user, invalidate_user,
    get_cached_post, cache_post, invalidate_post,
    get_cached_user_posts, cache_user_posts,
    warm_user_cache, warm_post_cache,
)
from auth.tokens import create_access_token, create_refresh_token, decode_token, revoke_token
from auth.permissions import can_edit_post, can_delete_user, can_manage_roles, require_permission
from utils.serializers import (
    serialize_user, serialize_user_full, serialize_post, serialize_post_summary,
    serialize_comment, paginated_response, success_response, error_response, wrap_envelope,
)
from utils.crypto import generate_api_key, mask_sensitive
from core.logging import info, warn
from core.errors import NotFoundError, ValidationError, raise_not_found, raise_validation


# ── Auth handlers ─────────────────────────────────────────────────────────────

@post("/auth/register", auth_required=False)
def register(request: dict) -> dict:
    body = request.get("body", {})
    data = validate_create_user(body)
    user = User.create(data["email"], data["password"], data["roles"])
    access = create_access_token(user.id, user.roles)
    refresh = create_refresh_token(user.id)
    info("user_registered", user_id=user.id)
    return _ok({"user": serialize_user(user), "access_token": access, "refresh_token": refresh}, 201)


@post("/auth/login", auth_required=False)
def login(request: dict) -> dict:
    body = request.get("body", {})
    email = validate_string("email", body.get("email", ""), 1, 254)
    password = validate_string("password", body.get("password", ""), 1, 128)
    user_data = get_user_by_email(email)
    if not user_data:
        return _err(401, "invalid_credentials", "email or password is incorrect")
    user = User(user_data)
    if not user.check_password(password):
        warn("login_failed", email=mask_sensitive(email))
        return _err(401, "invalid_credentials", "email or password is incorrect")
    access = create_access_token(user.id, user.roles)
    refresh = create_refresh_token(user.id)
    info("user_login", user_id=user.id)
    return _ok({"access_token": access, "refresh_token": refresh})


@post("/auth/refresh", auth_required=False)
def refresh_token(request: dict) -> dict:
    body = request.get("body", {})
    token = validate_string("refresh_token", body.get("refresh_token", ""), 1, 512)
    payload = decode_token(token)
    if not payload or payload.get("type") != "refresh":
        return _err(401, "invalid_token", "refresh token is invalid or expired")
    user = User.find(payload["sub"])
    new_access = create_access_token(user.id, user.roles)
    return _ok({"access_token": new_access})


@post("/auth/logout")
def logout(request: dict) -> dict:
    user = request.get("_user", {})
    token = request.get("headers", {}).get("authorization", "").removeprefix("Bearer ")
    if token:
        revoke_token(token)
    info("user_logout", user_id=user.get("sub"))
    return _ok({"message": "logged out"})


# ── User handlers ─────────────────────────────────────────────────────────────

@get("/users")
def list_users(request: dict) -> dict:
    require_permission(request.get("_user", {}), "admin")
    params = request.get("query", {})
    limit, offset = parse_pagination(params)
    # In a real system this would query with pagination
    return _ok(paginated_response([], serialize_user, 0, limit, offset))


@get("/users/:id")
def get_user(request: dict) -> dict:
    user_id = request.get("_params", {}).get("id")
    cached = get_cached_user(user_id)
    if cached:
        return _ok(cached)
    user = User.find(user_id)
    data = serialize_user_full(user)
    cache_user(user_id, data)
    return _ok(data)


@put("/users/:id")
def update_user(request: dict) -> dict:
    user_id = request.get("_params", {}).get("id")
    current_user = request.get("_user", {})
    if current_user.get("sub") != user_id and "admin" not in current_user.get("roles", []):
        return _err(403, "forbidden", "cannot update another user's profile")
    body = request.get("body", {})
    user = User.find(user_id)
    fields = {}
    if "email" in body:
        fields["email"] = validate_string("email", body["email"], 1, 254)
    if "roles" in body:
        if not can_manage_roles(current_user):
            return _err(403, "forbidden", "cannot change roles")
        fields["roles"] = body["roles"]
    updated = user.update(**fields)
    invalidate_user(user_id)
    info("user_updated", user_id=user_id)
    return _ok(serialize_user_full(updated))


@delete("/users/:id")
def delete_user(request: dict) -> dict:
    user_id = request.get("_params", {}).get("id")
    current_user = request.get("_user", {})
    if not can_delete_user(current_user):
        return _err(403, "forbidden", "admin role required")
    user = User.find(user_id)
    user.delete()
    invalidate_user(user_id)
    info("user_deleted", user_id=user_id)
    return _ok({"deleted": user_id})


@get("/users/:id/posts")
def get_user_posts(request: dict) -> dict:
    user_id = request.get("_params", {}).get("id")
    cached = get_cached_user_posts(user_id)
    if cached:
        return _ok(cached)
    params = request.get("query", {})
    limit, offset = parse_pagination(params)
    posts = Post.list(author_id=user_id, limit=limit, offset=offset)
    data = [serialize_post_summary(p) for p in posts]
    cache_user_posts(user_id, data)
    return _ok(data)


@post("/users/:id/api-key")
def generate_user_api_key(request: dict) -> dict:
    user_id = request.get("_params", {}).get("id")
    current_user = request.get("_user", {})
    if current_user.get("sub") != user_id:
        return _err(403, "forbidden", "can only generate key for yourself")
    key = generate_api_key()
    info("api_key_generated", user_id=user_id)
    return _ok({"api_key": key})


# ── Post handlers ─────────────────────────────────────────────────────────────

@get("/posts", auth_required=False)
def list_posts(request: dict) -> dict:
    params = request.get("query", {})
    limit, offset = parse_pagination(params)
    posts = Post.list(limit=limit, offset=offset)
    return _ok([serialize_post_summary(p) for p in posts])


@post("/posts")
def create_post(request: dict) -> dict:
    user = request.get("_user", {})
    body = request.get("body", {})
    data = validate_create_post(body)
    data["body"] = sanitize_html(data["body"])
    post = Post.create(
        author_id=user.get("sub"),
        title=data["title"],
        body=data["body"],
        tags=data["tags"],
    )
    info("post_created", post_id=post.id, author_id=post.author_id)
    return _ok(serialize_post(post), 201)


@get("/posts/:id", auth_required=False)
def get_post(request: dict) -> dict:
    post_id = request.get("_params", {}).get("id")

    def fetch(pid):
        return Post.find(pid).to_dict()

    data = warm_post_cache(post_id, fetch)
    if not data:
        raise_not_found("Post", post_id)
    return _ok(data)


@patch("/posts/:id")
def update_post(request: dict) -> dict:
    post_id = request.get("_params", {}).get("id")
    current_user = request.get("_user", {})
    post = Post.find(post_id)
    if not can_edit_post(current_user, post.author_id):
        return _err(403, "forbidden", "cannot edit another user's post")
    body = request.get("body", {})
    fields = {}
    if "title" in body:
        fields["title"] = validate_string("title", body["title"], 1, 200)
    if "body" in body:
        fields["body"] = sanitize_html(validate_string("body", body["body"], 1, 100_000))
    if "tags" in body:
        fields["tags"] = body["tags"]
    updated = post.update(**fields)
    invalidate_post(post_id, post.author_id)
    info("post_updated", post_id=post_id)
    return _ok(serialize_post(updated))


@delete("/posts/:id")
def delete_post(request: dict) -> dict:
    post_id = request.get("_params", {}).get("id")
    current_user = request.get("_user", {})
    post = Post.find(post_id)
    if not can_edit_post(current_user, post.author_id):
        return _err(403, "forbidden", "cannot delete another user's post")
    post.delete()
    invalidate_post(post_id, post.author_id)
    info("post_deleted", post_id=post_id)
    return _ok({"deleted": post_id})


@get("/posts/:id/comments", auth_required=False)
def get_comments(request: dict) -> dict:
    post_id = request.get("_params", {}).get("id")
    post = Post.find(post_id)
    comments = post.comments()
    return _ok([serialize_comment(c) for c in comments])


@post("/posts/:id/comments")
def add_comment(request: dict) -> dict:
    post_id = request.get("_params", {}).get("id")
    current_user = request.get("_user", {})
    body = request.get("body", {})
    text = validate_string("body", body.get("body", ""), 1, 10_000)
    post = Post.find(post_id)
    comment = post.add_comment(current_user.get("sub"), text)
    invalidate_post(post_id)
    info("comment_added", post_id=post_id, author_id=current_user.get("sub"))
    return _ok(serialize_comment(comment), 201)


@post("/posts/bulk-tag")
def bulk_tag(request: dict) -> dict:
    require_permission(request.get("_user", {}), "admin")
    body = request.get("body", {})
    post_ids = body.get("post_ids", [])
    tag = validate_string("tag", body.get("tag", ""), 1, 50)
    if not isinstance(post_ids, list) or len(post_ids) > 100:
        raise_validation("post_ids", "must be a list of up to 100 ids")
    updated = bulk_tag_posts(post_ids, tag)
    info("bulk_tag_applied", tag=tag, count=updated)
    return _ok({"updated": updated})


# ── Search handlers ───────────────────────────────────────────────────────────

@get("/search", auth_required=False)
def search(request: dict) -> dict:
    params = request.get("query", {})
    validated = validate_search_params(params)
    results = search_posts(validated["q"])
    posts = [serialize_post_summary(Post(r)) for r in results]
    return _ok(wrap_envelope(posts, {"query": validated["q"], "count": len(posts)}))


# ── Health / meta handlers ────────────────────────────────────────────────────

@get("/health", auth_required=False)
def health(request: dict) -> dict:
    return _ok({"status": "ok", "version": "1.0.0"})


@get("/routes", auth_required=True, roles=["admin"])
def list_all_routes(request: dict) -> dict:
    from api.router import list_routes
    return _ok(list_routes())


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ok(data, status: int = 200) -> dict:
    return {"status": status, "body": data}


def _err(status: int, code: str, message: str) -> dict:
    return {"status": status, "body": error_response(code, message)}
