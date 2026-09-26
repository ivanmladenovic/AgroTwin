from pydantic import EmailStr

from app.schemas.common import IDSchema


class UserRead(IDSchema):
    email: EmailStr
    full_name: str
    is_active: bool
    is_superuser: bool = False
