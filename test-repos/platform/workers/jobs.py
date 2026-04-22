from typing import Any
from core.logging import info, warn
from core.errors import NotFoundError
from db.models import User, Post
from db.queries import bulk_tag_posts, get_posts
from cache.invalidation import invalidate_user, invalidate_post, warm_user_cache, warm_post_cache
from utils.serializers import serialize_post_summary
from utils.crypto import generate_token, hash_token
from workers.queue import enqueue


# ── Job type constants ────────────────────────────────────────────────────────

JOB_SEND_EMAIL        = "send_email"
JOB_RESIZE_IMAGE      = "resize_image"
JOB_EXPORT_USER_DATA  = "export_user_data"
JOB_PURGE_USER        = "purge_user"
JOB_REINDEX_POST      = "reindex_post"
JOB_BULK_NOTIFY       = "bulk_notify"
JOB_DAILY_DIGEST      = "daily_digest"
JOB_RECALC_STATS      = "recalc_stats"
JOB_PRUNE_CACHE       = "prune_cache"
JOB_WARMUP_CACHE      = "warmup_cache"


# ── Job handlers (called by executor) ────────────────────────────────────────

def handle_send_email(payload: dict) -> Any:
    to = payload.get("to")
    subject = payload.get("subject", "(no subject)")
    body = payload.get("body", "")
    # Stub: in production this would call an SMTP or SES client
    info("email_sent", to=to, subject=subject, body_len=len(body))
    return {"delivered": True, "to": to}


def handle_resize_image(payload: dict) -> Any:
    image_id = payload.get("image_id")
    sizes = payload.get("sizes", [128, 256, 512])
    results = []
    for size in sizes:
        # Stub: would invoke PIL or a media service
        results.append({"size": size, "path": f"/media/{image_id}/{size}.webp"})
    info("image_resized", image_id=image_id, variants=len(results))
    return {"variants": results}


def handle_export_user_data(payload: dict) -> Any:
    user_id = payload.get("user_id")
    try:
        user = User.find(user_id)
    except NotFoundError:
        warn("export_user_not_found", user_id=user_id)
        return {"error": "user not found"}
    posts = Post.list(author_id=user_id, limit=1000)
    export = {
        "user": user.to_dict(include_roles=True),
        "posts": [serialize_post_summary(p) for p in posts],
    }
    token = generate_token()
    info("user_data_exported", user_id=user_id, post_count=len(posts))
    return {"download_token": token, "record_count": len(posts) + 1}


def handle_purge_user(payload: dict) -> Any:
    user_id = payload.get("user_id")
    try:
        user = User.find(user_id)
        posts = Post.list(author_id=user_id, limit=1000)
        for post in posts:
            post.delete()
            invalidate_post(post.id, user_id)
        user.delete()
        invalidate_user(user_id)
        info("user_purged", user_id=user_id, posts_deleted=len(posts))
        return {"purged": True, "posts_deleted": len(posts)}
    except NotFoundError:
        warn("purge_user_not_found", user_id=user_id)
        return {"purged": False}


def handle_reindex_post(payload: dict) -> Any:
    post_id = payload.get("post_id")
    try:
        post = Post.find(post_id)
        # Stub: would push to Elasticsearch or similar
        info("post_reindexed", post_id=post_id, title=post.title)
        return {"indexed": True, "post_id": post_id}
    except NotFoundError:
        warn("reindex_post_not_found", post_id=post_id)
        return {"indexed": False}


def handle_bulk_notify(payload: dict) -> Any:
    user_ids = payload.get("user_ids", [])
    message = payload.get("message", "")
    sent = 0
    for user_id in user_ids:
        enqueue(JOB_SEND_EMAIL, {
            "to": user_id,
            "subject": "Notification",
            "body": message,
        }, priority=3)
        sent += 1
    info("bulk_notify_enqueued", count=sent)
    return {"enqueued": sent}


def handle_daily_digest(payload: dict) -> Any:
    limit = payload.get("limit", 10)
    posts = get_posts(limit=limit, offset=0)
    digest_items = len(posts)
    # Stub: would compose and send a digest email
    info("daily_digest_prepared", items=digest_items)
    return {"items": digest_items}


def handle_recalc_stats(payload: dict) -> Any:
    # Stub: would aggregate metrics into a stats table
    info("stats_recalculated")
    return {"recalculated": True}


def handle_prune_cache(payload: dict) -> Any:
    from cache.redis_client import flush_pattern, stats
    pattern = payload.get("pattern", "post:*")
    removed = flush_pattern(pattern)
    info("cache_pruned", pattern=pattern, removed=removed)
    return {"removed": removed, "stats": stats()}


def handle_warmup_cache(payload: dict) -> Any:
    user_ids = payload.get("user_ids", [])
    warmed = 0
    for user_id in user_ids:
        warm_user_cache(user_id, lambda uid: User.find(uid).to_dict())
        warmed += 1
    info("cache_warmed", count=warmed)
    return {"warmed": warmed}


# ── Registry ─────────────────────────────────────────────────────────────────

HANDLERS = {
    JOB_SEND_EMAIL:       handle_send_email,
    JOB_RESIZE_IMAGE:     handle_resize_image,
    JOB_EXPORT_USER_DATA: handle_export_user_data,
    JOB_PURGE_USER:       handle_purge_user,
    JOB_REINDEX_POST:     handle_reindex_post,
    JOB_BULK_NOTIFY:      handle_bulk_notify,
    JOB_DAILY_DIGEST:     handle_daily_digest,
    JOB_RECALC_STATS:     handle_recalc_stats,
    JOB_PRUNE_CACHE:      handle_prune_cache,
    JOB_WARMUP_CACHE:     handle_warmup_cache,
}


def dispatch_job(job: dict) -> Any:
    job_type = job.get("type")
    handler = HANDLERS.get(job_type)
    if not handler:
        warn("unknown_job_type", job_type=job_type)
        raise ValueError(f"no handler registered for job type: {job_type}")
    return handler(job.get("payload", {}))
