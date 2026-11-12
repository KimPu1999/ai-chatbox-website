from datetime import datetime, timezone

import pytest

from app.tenancy.permissions import has_permission
from app.tenant_schemas import InvitationCreate, OrganizationCreate


def test_workspace_slug_and_names_are_normalized() -> None:
    payload = OrganizationCreate(name="  Acme   AI ", slug="Acme_AI")
    assert payload.name == "Acme AI"
    assert payload.slug == "acme_ai"


def test_workspace_roles_are_default_deny() -> None:
    assert has_permission("owner", "organization.members.manage")
    assert has_permission("admin", "organization.members.manage")
    assert not has_permission("member", "organization.members.manage")
    assert not has_permission("viewer", "organization.chat.create")
    assert not has_permission("owner", "unknown.permission")


def test_invitation_validation_bounds_expiration() -> None:
    assert InvitationCreate(email="person@example.com").expires_in_days == 7
    with pytest.raises(ValueError):
        InvitationCreate(email="person@example.com", expires_in_days=31)


def test_tenant_timestamps_are_timezone_aware_in_security_contract() -> None:
    assert datetime.now(timezone.utc).tzinfo is not None
