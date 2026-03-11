"""Main application entry point."""

from auth import authenticate, authorize
from handlers import handle_user_request, handle_admin_request
from middleware import log_request, rate_limit


def create_app():
    """Initialize the application."""
    config = load_config()
    db = setup_database(config)
    return App(config, db)


def load_config():
    """Load application configuration."""
    import os

    return {
        "debug": os.getenv("DEBUG", "false") == "true",
        "db_url": os.getenv("DATABASE_URL", "sqlite:///app.db"),
        "secret": os.getenv("SECRET_KEY", "changeme"),
    }


def setup_database(config):
    """Set up database connection."""
    return {"url": config["db_url"], "connected": True}


class App:
    """Main application class."""

    def __init__(self, config, db):
        self.config = config
        self.db = db
        self.routes = {}

    def route(self, path):
        def decorator(fn):
            self.routes[path] = fn
            return fn
        return decorator

    def dispatch(self, request):
        """Route a request to its handler."""
        log_request(request)

        if not rate_limit(request):
            return {"status": 429, "error": "Rate limited"}

        if not authenticate(request):
            return {"status": 401, "error": "Unauthorized"}

        path = request.get("path", "/")
        handler = self.routes.get(path)
        if handler:
            return handler(request)
        return {"status": 404, "error": "Not found"}
