import fastapi
from backend.services.auth import require_auth
from backend.models.user import get_user, create_user, delete_user, list_users
from shared.utils.validators import validate_email, validate_password
from shared.utils.helpers import paginate, format_response

router = fastapi.APIRouter()


@router.get("/")
def get_users(page: int = 1, limit: int = 20):
    users = list_users()
    return format_response(paginate(users, page, limit))


@router.get("/{user_id}")
def get_user_by_id(user_id: str, auth=fastapi.Depends(require_auth)):
    user = get_user(user_id)
    if not user:
        raise fastapi.HTTPException(status_code=404, detail="User not found")
    return format_response(user)


@router.post("/")
def create_new_user(email: str, password: str):
    if not validate_email(email):
        raise fastapi.HTTPException(status_code=400, detail="Invalid email")
    if not validate_password(password):
        raise fastapi.HTTPException(status_code=400, detail="Weak password")
    user = create_user(email, password)
    return format_response(user)


@router.delete("/{user_id}")
def remove_user(user_id: str, auth=fastapi.Depends(require_auth)):
    success = delete_user(user_id)
    if not success:
        raise fastapi.HTTPException(status_code=404)
    return {"deleted": user_id}
