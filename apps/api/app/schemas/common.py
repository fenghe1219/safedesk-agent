from pydantic import BaseModel


class NavItem(BaseModel):
    key: str
    label: str
    href: str
    icon: str


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: str
    role_label: str
    department: str


class MeResponse(BaseModel):
    user: UserOut
    permissions: dict[str, bool]
    navigation: list[NavItem]
    demo_mode: bool
    csrf_token: str
    default_path: str


class HealthResponse(BaseModel):
    status: str
    database: str
    version: str
    app_env: str
