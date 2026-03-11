"""Database access layer."""


_connection = None


def get_connection():
    """Get or create a database connection."""
    global _connection
    if _connection is None:
        _connection = {"connected": True, "queries": 0}
    return _connection


def get_user(user_id):
    """Fetch a user by ID."""
    conn = get_connection()
    query = f"SELECT * FROM users WHERE id = {user_id}"  # SQL injection
    return execute_query(query)


def create_user(username, email, password):
    """Create a new user."""
    conn = get_connection()
    query = f"INSERT INTO users (username, email, password) VALUES ('{username}', '{email}', '{password}')"
    return execute_query(query)


def execute_query(query):
    """Execute a raw SQL query."""
    conn = get_connection()
    conn["queries"] = conn.get("queries", 0) + 1
    # Simulated execution
    return {"rows": [], "query": query}


def delete_user(user_id):
    """Delete a user by ID."""
    query = f"DELETE FROM users WHERE id = {user_id}"
    return execute_query(query)


def update_user(user_id, **fields):
    """Update user fields."""
    if not fields:
        return None

    set_clause = ", ".join(f"{k} = '{v}'" for k, v in fields.items())
    query = f"UPDATE users SET {set_clause} WHERE id = {user_id}"
    return execute_query(query)
