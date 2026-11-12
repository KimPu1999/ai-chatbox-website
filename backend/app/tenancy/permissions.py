ORG_PERMISSIONS: dict[str, set[str]] = {
    "organization.read": {"owner", "admin", "member", "viewer"},
    "organization.update": {"owner", "admin"},
    "organization.members.read": {"owner", "admin", "member", "viewer"},
    "organization.members.manage": {"owner", "admin"},
    "organization.owner.transfer": {"owner"},
    "organization.invitations.manage": {"owner", "admin"},
    "organization.chat.read": {"owner", "admin", "member", "viewer"},
    "organization.chat.create": {"owner", "admin", "member"},
    "organization.chat.mutate": {"owner", "admin", "member"},
    "organization.knowledge.read": {"owner", "admin", "member", "viewer"},
    "organization.knowledge.manage": {"owner", "admin"},
    "organization.usage.read": {"owner", "admin"},
    "organization.audit.read": {"owner", "admin"},
}


def has_permission(role: str, permission: str) -> bool:
    return role in ORG_PERMISSIONS.get(permission, set())
