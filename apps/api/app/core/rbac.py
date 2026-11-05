from enum import StrEnum


class Role(StrEnum):
    EMPLOYEE = "employee"
    SUPPORT = "support"
    APPROVER = "approver"
    ADMIN = "admin"
    EVALUATOR = "evaluator"
    AUDITOR = "auditor"


ROLE_LABELS: dict[str, str] = {
    Role.EMPLOYEE: "员工",
    Role.SUPPORT: "支持专员",
    Role.APPROVER: "审批人",
    Role.ADMIN: "管理员",
    Role.EVALUATOR: "评估员",
    Role.AUDITOR: "审计员",
}

ALL_PERMISSIONS = (
    "case:create",
    "case:read",
    "case:read_all",
    "ticket:view",
    "ticket:manage",
    "approval:view",
    "approval:decide",
    "knowledge:view",
    "knowledge:manage",
    "eval:manage",
    "audit:view",
    "dashboard:view",
    "settings:manage",
)

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    Role.EMPLOYEE: frozenset({"case:create", "case:read", "ticket:view"}),
    Role.SUPPORT: frozenset(
        {
            "case:create",
            "case:read",
            "case:read_all",
            "ticket:view",
            "ticket:manage",
            "dashboard:view",
        }
    ),
    Role.APPROVER: frozenset(
        {
            "case:create",
            "case:read",
            "case:read_all",
            "ticket:view",
            "approval:view",
            "approval:decide",
            "dashboard:view",
        }
    ),
    Role.ADMIN: frozenset(
        {
            "case:create",
            "case:read",
            "case:read_all",
            "ticket:view",
            "ticket:manage",
            "approval:view",
            "knowledge:view",
            "knowledge:manage",
            "eval:manage",
            "audit:view",
            "dashboard:view",
            "settings:manage",
        }
    ),
    Role.EVALUATOR: frozenset({"knowledge:view", "eval:manage"}),
    Role.AUDITOR: frozenset({"case:read", "case:read_all", "audit:view", "dashboard:view"}),
}

NAV_ITEMS: dict[str, list[dict[str, str]]] = {
    Role.EMPLOYEE: [
        {"key": "chat", "label": "工作台", "href": "/chat", "icon": "workbench"},
        {"key": "tickets", "label": "我的工单", "href": "/tickets", "icon": "ticket"},
    ],
    Role.SUPPORT: [
        {"key": "chat", "label": "工作台", "href": "/chat", "icon": "workbench"},
        {"key": "tickets", "label": "工单", "href": "/tickets", "icon": "ticket"},
        {"key": "dashboard", "label": "看板", "href": "/dashboard", "icon": "chart"},
    ],
    Role.APPROVER: [
        {"key": "chat", "label": "工作台", "href": "/chat", "icon": "workbench"},
        {"key": "tickets", "label": "工单", "href": "/tickets", "icon": "ticket"},
        {"key": "approvals", "label": "审批", "href": "/approvals", "icon": "shield"},
        {"key": "dashboard", "label": "看板", "href": "/dashboard", "icon": "chart"},
    ],
    Role.ADMIN: [
        {"key": "chat", "label": "工作台", "href": "/chat", "icon": "workbench"},
        {"key": "tickets", "label": "工单", "href": "/tickets", "icon": "ticket"},
        {"key": "approvals", "label": "审批", "href": "/approvals", "icon": "shield"},
        {"key": "knowledge", "label": "知识", "href": "/knowledge", "icon": "book"},
        {"key": "evaluations", "label": "评估", "href": "/evaluations", "icon": "flask"},
        {"key": "audit", "label": "审计", "href": "/audit", "icon": "audit"},
        {"key": "dashboard", "label": "看板", "href": "/dashboard", "icon": "chart"},
        {"key": "settings", "label": "配置", "href": "/settings", "icon": "settings"},
    ],
    Role.EVALUATOR: [
        {"key": "knowledge", "label": "知识", "href": "/knowledge", "icon": "book"},
        {"key": "evaluations", "label": "评估", "href": "/evaluations", "icon": "flask"},
    ],
    Role.AUDITOR: [
        {"key": "audit", "label": "审计", "href": "/audit", "icon": "audit"},
        {"key": "dashboard", "label": "看板", "href": "/dashboard", "icon": "chart"},
    ],
}

DEFAULT_PATHS: dict[str, str] = {
    Role.EMPLOYEE: "/chat",
    Role.SUPPORT: "/tickets",
    Role.APPROVER: "/approvals",
    Role.ADMIN: "/dashboard",
    Role.EVALUATOR: "/evaluations",
    Role.AUDITOR: "/audit",
}


def permissions_for(role: str) -> dict[str, bool]:
    allowed = ROLE_PERMISSIONS.get(role, frozenset())
    return {key: key in allowed for key in ALL_PERMISSIONS}


def navigation_for(role: str) -> list[dict[str, str]]:
    return NAV_ITEMS.get(role, [])


def default_path_for(role: str) -> str:
    return DEFAULT_PATHS.get(role, "/login")


def has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())
