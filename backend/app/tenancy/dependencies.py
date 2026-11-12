# ruff: noqa: E501

from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_verified_user
from app.db import get_db
from app.models import Organization, OrganizationMembership, User
from app.tenancy.context import set_transaction_organization
from app.tenancy.permissions import has_permission


@dataclass(frozen=True)
class OrganizationContext:
    organization: Organization
    membership: OrganizationMembership


async def get_organization_context(
    organization_id: UUID,
    user: User = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationContext:
    # Set the requested selector before querying. Membership verification below
    # remains authoritative; the selector alone never grants access.
    await set_transaction_organization(db, organization_id)
    organization = await db.scalar(
        select(Organization).where(Organization.id == organization_id, Organization.status == "active")
    )
    membership = await db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.status == "active",
        )
    )
    if organization is None or membership is None:
        raise HTTPException(status_code=404, detail={"code": "WORKSPACE_NOT_FOUND", "message": "Workspace not found"})
    return OrganizationContext(organization=organization, membership=membership)


def require_organization_permission(permission: str) -> Callable:
    async def dependency(
        context: OrganizationContext = Depends(get_organization_context),
    ) -> OrganizationContext:
        if not has_permission(context.membership.role, permission):
            raise HTTPException(status_code=403, detail={"code": "WORKSPACE_FORBIDDEN", "message": "Workspace permission denied"})
        return context

    return dependency


def require_organization_role(*roles: str) -> Callable:
    async def dependency(
        context: OrganizationContext = Depends(get_organization_context),
    ) -> OrganizationContext:
        if context.membership.role not in roles:
            raise HTTPException(status_code=403, detail={"code": "WORKSPACE_FORBIDDEN", "message": "Workspace role denied"})
        return context

    return dependency
