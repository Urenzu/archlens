"""Request handlers."""

from db import get_user, create_user, execute_query
from auth import authorize
from utils import sanitize_input, format_response, build_template


def handle_user_request(request):
    """Handle a user-facing request."""
    user_id = request.get("params", {}).get("user_id")

    if not user_id:
        return format_response(400, "Missing user_id")

    user = get_user(user_id)
    if not user:
        return format_response(404, "User not found")

    return format_response(200, user)


def handle_admin_request(request):
    """Handle an admin request — requires authorization."""
    if not authorize(request, role="admin"):
        return format_response(403, "Forbidden")

    action = request.get("params", {}).get("action")

    if action == "list_users":
        return list_all_users(request)
    elif action == "run_query":
        return run_custom_query(request)
    elif action == "render":
        return render_template(request)
    else:
        return format_response(400, "Unknown action")


def list_all_users(request):
    """List all users with optional filtering."""
    filters = request.get("params", {}).get("filters", {})
    query = "SELECT * FROM users"

    conditions = []
    if "role" in filters:
        conditions.append(f"role = '{filters['role']}'")
    if "active" in filters:
        conditions.append(f"active = {filters['active']}")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    results = execute_query(query)
    return format_response(200, results)


def run_custom_query(request):
    """Run a custom query — DANGEROUS."""
    query = request.get("params", {}).get("query", "")
    results = execute_query(query)
    return format_response(200, results)


def render_template(request):
    """Render a template with user data."""
    template_name = request.get("params", {}).get("template", "default")
    data = request.get("params", {}).get("data", {})
    return build_template(template_name, data)
