from typing import Callable
from core.logging import info, warn
from core.errors import NotFoundError, ValidationError, AuthError, RateLimitError
from auth.middleware import authenticate_request, rate_limit_check
from utils.serializers import error_response


_routes: dict = {"GET": {}, "POST": {}, "PUT": {}, "PATCH": {}, "DELETE": {}}


def route(method: str, path: str, auth_required: bool = True, roles: list = None):
    def decorator(fn: Callable) -> Callable:
        _routes[method.upper()][path] = {
            "handler": fn,
            "auth_required": auth_required,
            "roles": roles or [],
        }
        return fn
    return decorator


def get(path: str, **kwargs):
    return route("GET", path, **kwargs)


def post(path: str, **kwargs):
    return route("POST", path, **kwargs)


def put(path: str, **kwargs):
    return route("PUT", path, **kwargs)


def patch(path: str, **kwargs):
    return route("PATCH", path, **kwargs)


def delete(path: str, **kwargs):
    return route("DELETE", path, **kwargs)


def dispatch(method: str, path: str, request: dict) -> dict:
    method = method.upper()
    route_map = _routes.get(method, {})

    handler_config = route_map.get(path)
    if handler_config is None:
        handler_config = _match_dynamic(method, path, request)
    if handler_config is None:
        warn("route_not_found", method=method, path=path)
        return _respond(404, error_response("not_found", f"{method} {path} not found"))

    if handler_config.get("auth_required"):
        try:
            user = authenticate_request(request)
            request["_user"] = user
        except AuthError as e:
            return _respond(401, error_response("unauthorized", str(e)))

    if handler_config.get("roles"):
        user = request.get("_user", {})
        if not _has_role(user, handler_config["roles"]):
            return _respond(403, error_response("forbidden", "insufficient permissions"))

    ip = request.get("ip", "unknown")
    if not rate_limit_check(ip):
        return _respond(429, error_response("rate_limited", "too many requests"))

    try:
        result = handler_config["handler"](request)
        info("request_handled", method=method, path=path)
        return result
    except ValidationError as e:
        return _respond(400, error_response("validation_error", str(e), getattr(e, "field", None)))
    except NotFoundError as e:
        return _respond(404, error_response("not_found", str(e)))
    except AuthError as e:
        return _respond(401, error_response("unauthorized", str(e)))
    except RateLimitError as e:
        return _respond(429, error_response("rate_limited", str(e)))
    except Exception as e:
        warn("unhandled_error", error=str(e))
        return _respond(500, error_response("internal_error", "an unexpected error occurred"))


def _match_dynamic(method: str, path: str, request: dict):
    parts = path.strip("/").split("/")
    for registered_path, config in _routes.get(method, {}).items():
        pattern_parts = registered_path.strip("/").split("/")
        if len(parts) != len(pattern_parts):
            continue
        params = {}
        matched = True
        for p, r in zip(parts, pattern_parts):
            if r.startswith(":"):
                params[r[1:]] = p
            elif p != r:
                matched = False
                break
        if matched:
            request["_params"] = params
            return config
    return None


def _has_role(user: dict, required_roles: list) -> bool:
    user_roles = user.get("roles", [])
    return any(r in user_roles for r in required_roles)


def _respond(status: int, body: dict) -> dict:
    return {"status": status, "body": body}


def list_routes() -> list[dict]:
    result = []
    for method, paths in _routes.items():
        for path, config in paths.items():
            result.append({
                "method": method,
                "path": path,
                "auth_required": config["auth_required"],
                "roles": config["roles"],
            })
    return result
