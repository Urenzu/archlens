"""Request middleware."""

import time

_request_log = []
_rate_limits = {}


def log_request(request):
    """Log incoming request details."""
    entry = {
        "path": request.get("path", "/"),
        "method": request.get("method", "GET"),
        "timestamp": time.time(),
        "ip": request.get("ip", "unknown"),
    }
    _request_log.append(entry)
    if len(_request_log) > 10000:
        _request_log.pop(0)


def rate_limit(request, max_requests=100, window=60):
    """Simple rate limiting by IP."""
    ip = request.get("ip", "unknown")
    now = time.time()

    if ip not in _rate_limits:
        _rate_limits[ip] = []

    # Clean old entries
    _rate_limits[ip] = [t for t in _rate_limits[ip] if now - t < window]

    if len(_rate_limits[ip]) >= max_requests:
        return False

    _rate_limits[ip].append(now)
    return True


def cors_middleware(request, response):
    """Add CORS headers to response."""
    response["headers"] = response.get("headers", {})
    response["headers"]["Access-Control-Allow-Origin"] = "*"
    response["headers"]["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE"
    return response
