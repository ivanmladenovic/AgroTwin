from sqlalchemy.orm import Session

from app.core.exceptions import UnauthorizedError
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import TokenResponse
from app.schemas.user import UserRead


class AuthService:
    def __init__(self, db: Session) -> None:
        self.users = UserRepository(db)

    def authenticate(self, email: str, password: str) -> TokenResponse:
        user = self.users.get_by_email(email)
        if user is None or not user.is_active or not verify_password(password, user.hashed_password):
            raise UnauthorizedError("Neispravna e-pošta ili lozinka")
        token = create_access_token(user.id, extra_claims={"email": user.email})
        return TokenResponse(access_token=token, user=UserRead.model_validate(user))

    def get_active_user(self, user_id: str) -> User:
        from uuid import UUID

        try:
            parsed_id = UUID(user_id)
        except ValueError as exc:
            raise UnauthorizedError("Neispravan token") from exc
        user = self.users.get_by_id(parsed_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("Korisnik nije pronađen ili nije aktivan")
        return user
