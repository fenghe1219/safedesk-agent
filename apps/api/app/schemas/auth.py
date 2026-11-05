from pydantic import BaseModel, Field

from app.core.rbac import Role


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=200)


class SwitchUserRequest(BaseModel):
    role: Role
