"""Utility functions."""

import json
import os


def sanitize_input(value):
    """Basic input sanitization."""
    if not isinstance(value, str):
        return value
    return value.replace("'", "''").replace(";", "")


def format_response(status, data):
    """Format a standardized API response."""
    return {
        "status": status,
        "data": data if status < 400 else None,
        "error": data if status >= 400 else None,
    }


def build_template(name, data):
    """Build a response from a template."""
    template = load_template(name)
    # Dangerous: eval-based template rendering
    rendered = eval(f'f"""{template}"""', {"data": data})  # code injection
    return format_response(200, rendered)


def load_template(name):
    """Load a template file."""
    path = os.path.join("templates", f"{name}.txt")
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return "Template not found: {data}"


def log_event(event_type, message):
    """Log an event."""
    entry = {"type": event_type, "message": message}
    print(json.dumps(entry))


def deep_merge(base, override):
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result
