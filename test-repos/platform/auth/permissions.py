from typing import Optional
from core.errors import ForbiddenError, raise_forbidden
from core.logging import debug, warn
from auth.tokens import extract_roles


ROLE_HIERARCHY = {
    "superadmin": 100,
    "admin": 80,
    "moderator": 60,
    "editor": 40,
    "viewer": 20,
    "guest": 0,
}

RESOURCE_PERMISSIONS: dict[str, dict[str, list[str]]] = {
    "user": {
        "read": ["viewer", "editor", "moderator", "admin", "superadmin"],
        "write": ["editor", "moderator", "admin", "superadmin"],
        "delete": ["admin", "superadmin"],
    },
    "post": {
        "read": ["guest", "viewer", "editor", "moderator", "admin", "superadmin"],
        "write": ["editor", "moderator", "admin", "superadmin"],
        "delete": ["moderator", "admin", "superadmin"],
    },
    "settings": {
        "read": ["admin", "superadmin"],
        "write": ["admin", "superadmin"],
        "delete": ["superadmin"],
    },
}


def has_role(roles: list[str], required: str) -> bool:
    required_level = ROLE_HIERARCHY.get(required, 0)
    for role in roles:
        if ROLE_HIERARCHY.get(role, -1) >= required_level:
            return True
    return False


def can_perform(roles: list[str], resource: str, action: str) -> bool:
    allowed = RESOURCE_PERMISSIONS.get(resource, {}).get(action, [])
    for role in roles:
        if role in allowed:
            debug("permission_granted", role=role, resource=resource, action=action)
            return True
    warn("permission_denied", roles=roles, resource=resource, action=action)
    return False


def require_permission(token: str, resource: str, action: str) -> None:
    roles = extract_roles(token)
    if not can_perform(roles, resource, action):
        raise_forbidden(action, resource)


def require_role(token: str, role: str) -> None:
    roles = extract_roles(token)
    if not has_role(roles, role):
        raise ForbiddenError(f"Role '{role}' or higher required")


def get_max_role(roles: list[str]) -> Optional[str]:
    best = None
    best_level = -1
    for role in roles:
        level = ROLE_HIERARCHY.get(role, -1)
        if level > best_level:
            best = role
            best_level = level
    return best


def is_admin(roles: list[str]) -> bool:
    return has_role(roles, "admin")


def is_superadmin(roles: list[str]) -> bool:
    return "superadmin" in roles


def filter_by_permission(items: list, roles: list[str], resource: str) -> list:
    if can_perform(roles, resource, "read"):
        return items
    return []


def build_permission_map(roles: list[str]) -> dict:
    result = {}
    for resource, actions in RESOURCE_PERMISSIONS.items():
        result[resource] = {
            action: can_perform(roles, resource, action)
            for action in actions
        }
    return result
