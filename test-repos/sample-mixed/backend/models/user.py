import sqlalchemy
from shared.utils.validators import validate_email
from shared.utils.helpers import hash_secret, new_id

_users: dict = {}


def get_user(user_id: str):
    return _users.get(user_id)


def get_user_by_email(email: str):
    for user in _users.values():
        if user.get("email") == email:
            return user
    return None


def create_user(email: str, password: str) -> dict:
    if not validate_email(email):
        raise ValueError("Invalid email")
    uid = new_id()
    hashed = hash_secret(password)
    user = {"id": uid, "email": email, "password": hashed, "role": "user"}
    _users[uid] = user
    persist_user(user)
    return user


def update_user(user_id: str, data: dict) -> dict:
    user = get_user(user_id)
    if not user:
        raise KeyError(user_id)
    user.update(data)
    persist_user(user)
    return user


def delete_user(user_id: str) -> bool:
    if user_id not in _users:
        return False
    del _users[user_id]
    evict_user(user_id)
    return True


def list_users() -> list:
    return list(_users.values())


def persist_user(user: dict):
    # Simulate DB write
    pass


def evict_user(user_id: str):
    # Simulate cache eviction
    pass
