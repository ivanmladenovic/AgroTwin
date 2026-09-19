from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserRead
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DBSession) -> TokenResponse:
    return AuthService(db).authenticate(payload.email, payload.password)


@router.get("/me", response_model=UserRead)
def me(current_user: CurrentUser) -> UserRead:
    return UserRead.model_validate(current_user)
