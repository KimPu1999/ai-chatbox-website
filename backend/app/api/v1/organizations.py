# ruff: noqa: E501

from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import ensure_trusted_origin, require_csrf, require_verified_user
from app.auth.security import generate_token, hash_token, utc_now
from app.core.config import get_settings
from app.db import get_db
from app.models import (
    Conversation,
    KnowledgeBase,
    Organization,
    OrganizationAuditLog,
    OrganizationInvitation,
    OrganizationMembership,
    OrganizationSetting,
    OrganizationSubscription,
    Plan,
    User,
)
from app.repositories.users import normalize_email
from app.schemas import ConversationCreate, ConversationRead
from app.tenancy.dependencies import OrganizationContext, require_organization_permission
from app.tenant_schemas import (
    InvitationCreate,
    InvitationCreated,
    InvitationRead,
    KnowledgeBaseCreate,
    KnowledgeBaseRead,
    MemberRead,
    MemberUpdate,
    OrganizationCreate,
    OrganizationRead,
    OrganizationSummary,
    OrganizationUpdate,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])
invitation_router = APIRouter(prefix="/invitations", tags=["organizations"])


def _slug(value: str) -> str:
    return value.strip().casefold()


async def _audit(db: AsyncSession, context: OrganizationContext, user_id: UUID, action: str, target_id: UUID | None = None) -> None:
    db.add(OrganizationAuditLog(organization_id=context.organization.id, actor_user_id=user_id, action=action, target_id=target_id))


@router.get("", response_model=list[OrganizationSummary])
async def list_organizations(user: User = Depends(require_verified_user), db: AsyncSession = Depends(get_db)) -> list[OrganizationSummary]:
    rows = await db.execute(
        select(Organization, OrganizationMembership.role)
        .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
        .where(OrganizationMembership.user_id == user.id, OrganizationMembership.status == "active", Organization.status == "active")
        .order_by(Organization.name.asc())
    )
    return [OrganizationSummary(id=org.id, slug=org.slug, name=org.name, status=org.status, role=role) for org, role in rows]


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreate,
    request: Request,
    user: User = Depends(require_verified_user),
    _: object = Depends(require_csrf),
    db: AsyncSession = Depends(get_db),
) -> OrganizationRead:
    ensure_trusted_origin(request)
    existing = await db.scalar(select(Organization.id).where(Organization.slug == _slug(payload.slug)))
    if existing:
        raise HTTPException(status_code=409, detail={"code": "WORKSPACE_SLUG_TAKEN", "message": "Workspace slug is already in use"})
    organization = Organization(owner_id=user.id, slug=_slug(payload.slug), name=payload.name, description=payload.description)
    db.add(organization)
    await db.flush()
    db.add(OrganizationMembership(organization_id=organization.id, user_id=user.id, role="owner", status="active"))
    db.add(OrganizationSetting(organization_id=organization.id, settings={}))
    free_plan = await db.scalar(select(Plan).where(Plan.code == "free"))
    if free_plan:
        db.add(OrganizationSubscription(organization_id=organization.id, plan_id=free_plan.id, billing_owner_id=user.id, status="active"))
    await db.commit()
    await db.refresh(organization)
    return OrganizationRead.model_validate({**organization.__dict__, "role": "owner"})


@router.get("/{organization_id}", response_model=OrganizationRead)
async def get_organization(context: OrganizationContext = Depends(require_organization_permission("organization.read"))) -> OrganizationRead:
    return OrganizationRead.model_validate({**context.organization.__dict__, "role": context.membership.role})


@router.patch("/{organization_id}", response_model=OrganizationRead)
async def update_organization(
    payload: OrganizationUpdate,
    request: Request,
    user: User = Depends(require_verified_user),
    _: object = Depends(require_csrf),
    context: OrganizationContext = Depends(require_organization_permission("organization.update")),
    db: AsyncSession = Depends(get_db),
) -> OrganizationRead:
    ensure_trusted_origin(request)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(context.organization, key, value)
    await _audit(db, context, user.id, "organization.updated", context.organization.id)
    await db.commit()
    await db.refresh(context.organization)
    return OrganizationRead.model_validate({**context.organization.__dict__, "role": context.membership.role})


@router.get("/{organization_id}/conversations", response_model=list[ConversationRead])
async def list_team_conversations(
    context: OrganizationContext = Depends(require_organization_permission("organization.chat.read")),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationRead]:
    rows = await db.scalars(
        select(Conversation)
        .where(Conversation.organization_id == context.organization.id, Conversation.deleted_at.is_(None))
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        .limit(100)
    )
    return [ConversationRead.model_validate(item) for item in rows]


@router.post("/{organization_id}/conversations", response_model=ConversationRead, status_code=201)
async def create_team_conversation(
    payload: ConversationCreate,
    request: Request,
    user: User = Depends(require_verified_user),
    _: object = Depends(require_csrf),
    context: OrganizationContext = Depends(require_organization_permission("organization.chat.create")),
    db: AsyncSession = Depends(get_db),
) -> ConversationRead:
    ensure_trusted_origin(request)
    item = Conversation(user_id=user.id, organization_id=context.organization.id, title=payload.title)
    db.add(item)
    await _audit(db, context, user.id, "conversation.created", item.id)
    await db.commit()
    await db.refresh(item)
    return ConversationRead.model_validate(item)


@router.post("/{organization_id}/transfer-ownership", response_model=MemberRead)
async def transfer_ownership(
    member_id: UUID,
    request: Request,
    user: User = Depends(require_verified_user),
    _: object = Depends(require_csrf),
    context: OrganizationContext = Depends(require_organization_permission("organization.owner.transfer")),
    db: AsyncSession = Depends(get_db),
) -> MemberRead:
    ensure_trusted_origin(request)
    target = await db.scalar(select(OrganizationMembership).where(OrganizationMembership.id == member_id, OrganizationMembership.organization_id == context.organization.id).with_for_update())
    current = await db.scalar(select(OrganizationMembership).where(OrganizationMembership.organization_id == context.organization.id, OrganizationMembership.user_id == user.id).with_for_update())
    if target is None or current is None or target.status != "active":
        raise HTTPException(status_code=404, detail="Member not found")
    target.role = "owner"
    current.role = "admin"
    context.organization.owner_id = target.user_id
    await _audit(db, context, user.id, "organization.ownership_transferred", target.user_id)
    await db.commit()
    row = await db.execute(select(OrganizationMembership, User).join(User, User.id == OrganizationMembership.user_id).where(OrganizationMembership.id == target.id))
    member, target_user = row.one()
    return MemberRead(id=member.id, user_id=target_user.id, email=target_user.email, display_name=target_user.display_name, role=member.role, status=member.status, created_at=member.created_at)


@router.get("/{organization_id}/members", response_model=list[MemberRead])
async def list_members(context: OrganizationContext = Depends(require_organization_permission("organization.members.read")), db: AsyncSession = Depends(get_db)) -> list[MemberRead]:
    rows = await db.execute(select(OrganizationMembership, User).join(User, User.id == OrganizationMembership.user_id).where(OrganizationMembership.organization_id == context.organization.id).order_by(OrganizationMembership.created_at.asc()))
    return [MemberRead(id=m.id, user_id=u.id, email=u.email, display_name=u.display_name, role=m.role, status=m.status, created_at=m.created_at) for m, u in rows]


@router.patch("/{organization_id}/members/{member_id}", response_model=MemberRead)
async def update_member(
    member_id: UUID,
    payload: MemberUpdate,
    request: Request,
    user: User = Depends(require_verified_user),
    _: object = Depends(require_csrf),
    context: OrganizationContext = Depends(require_organization_permission("organization.members.manage")),
    db: AsyncSession = Depends(get_db),
) -> MemberRead:
    ensure_trusted_origin(request)
    member = await db.scalar(select(OrganizationMembership).where(OrganizationMembership.id == member_id, OrganizationMembership.organization_id == context.organization.id).with_for_update())
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.user_id == user.id and payload.role and payload.role != member.role:
        raise HTTPException(status_code=403, detail={"code": "SELF_ROLE_CHANGE_DENIED", "message": "You cannot change your own role"})
    if member.role == "owner" and (payload.status == "suspended" or payload.role not in (None, "owner")):
        owners = await db.scalar(select(func.count(OrganizationMembership.id)).where(OrganizationMembership.organization_id == context.organization.id, OrganizationMembership.role == "owner", OrganizationMembership.status == "active"))
        if int(owners or 0) <= 1:
            raise HTTPException(status_code=409, detail={"code": "LAST_OWNER_PROTECTED", "message": "The last active owner cannot be removed or demoted"})
    if payload.role:
        if payload.role == "owner" and context.membership.role != "owner":
            raise HTTPException(status_code=403, detail="Only an owner can assign ownership")
        member.role = payload.role
    if payload.status:
        member.status = payload.status
    await _audit(db, context, user.id, "membership.updated", member.user_id)
    await db.commit()
    row = await db.execute(select(OrganizationMembership, User).join(User, User.id == OrganizationMembership.user_id).where(OrganizationMembership.id == member.id))
    m, u = row.one()
    return MemberRead(id=m.id, user_id=u.id, email=u.email, display_name=u.display_name, role=m.role, status=m.status, created_at=m.created_at)


@router.delete("/{organization_id}/members/{member_id}", status_code=204)
async def remove_member(member_id: UUID, request: Request, user: User = Depends(require_verified_user), _: object = Depends(require_csrf), context: OrganizationContext = Depends(require_organization_permission("organization.members.manage")), db: AsyncSession = Depends(get_db)) -> None:
    ensure_trusted_origin(request)
    member = await db.scalar(select(OrganizationMembership).where(OrganizationMembership.id == member_id, OrganizationMembership.organization_id == context.organization.id).with_for_update())
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    if member.role == "owner":
        owners = await db.scalar(select(func.count(OrganizationMembership.id)).where(OrganizationMembership.organization_id == context.organization.id, OrganizationMembership.role == "owner", OrganizationMembership.status == "active"))
        if int(owners or 0) <= 1:
            raise HTTPException(status_code=409, detail={"code": "LAST_OWNER_PROTECTED", "message": "The last active owner cannot be removed"})
    member.status = "removed"
    await _audit(db, context, user.id, "membership.removed", member.user_id)
    await db.commit()


@router.post("/{organization_id}/invitations", response_model=InvitationCreated, status_code=201)
async def create_invitation(payload: InvitationCreate, request: Request, user: User = Depends(require_verified_user), _: object = Depends(require_csrf), context: OrganizationContext = Depends(require_organization_permission("organization.invitations.manage")), db: AsyncSession = Depends(get_db)) -> InvitationCreated:
    ensure_trusted_origin(request)
    email = normalize_email(payload.email)
    existing = await db.scalar(select(OrganizationMembership.id).join(User, User.id == OrganizationMembership.user_id).where(OrganizationMembership.organization_id == context.organization.id, User.email_normalized == email, OrganizationMembership.status == "active"))
    if existing:
        raise HTTPException(status_code=409, detail="User is already a member")
    pending = await db.scalar(select(OrganizationInvitation.id).where(OrganizationInvitation.organization_id == context.organization.id, OrganizationInvitation.email_normalized == email, OrganizationInvitation.accepted_at.is_(None), OrganizationInvitation.revoked_at.is_(None), OrganizationInvitation.expires_at > utc_now()))
    if pending:
        raise HTTPException(status_code=409, detail="An active invitation already exists")
    token = generate_token()
    invitation = OrganizationInvitation(organization_id=context.organization.id, invited_by=user.id, email_normalized=email, role=payload.role, token_hash=hash_token(token), expires_at=utc_now() + timedelta(days=payload.expires_in_days))
    db.add(invitation)
    await _audit(db, context, user.id, "invitation.created", invitation.id)
    await db.commit()
    await db.refresh(invitation)
    exposed = token if get_settings().environment in {"development", "test"} else None
    return InvitationCreated(invitation=InvitationRead.model_validate(invitation), token=exposed)


@router.get("/{organization_id}/invitations", response_model=list[InvitationRead])
async def list_invitations(context: OrganizationContext = Depends(require_organization_permission("organization.invitations.manage")), db: AsyncSession = Depends(get_db)) -> list[InvitationRead]:
    rows = await db.scalars(select(OrganizationInvitation).where(OrganizationInvitation.organization_id == context.organization.id).order_by(OrganizationInvitation.created_at.desc()).limit(100))
    return [InvitationRead.model_validate(item) for item in rows]


@router.delete("/{organization_id}/invitations/{invitation_id}", status_code=204)
async def revoke_invitation(invitation_id: UUID, request: Request, user: User = Depends(require_verified_user), _: object = Depends(require_csrf), context: OrganizationContext = Depends(require_organization_permission("organization.invitations.manage")), db: AsyncSession = Depends(get_db)) -> None:
    ensure_trusted_origin(request)
    invitation = await db.scalar(select(OrganizationInvitation).where(OrganizationInvitation.id == invitation_id, OrganizationInvitation.organization_id == context.organization.id).with_for_update())
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    invitation.revoked_at = utc_now()
    await _audit(db, context, user.id, "invitation.revoked", invitation.id)
    await db.commit()


@router.post("/{organization_id}/invitations/{invitation_id}/resend", response_model=InvitationCreated)
async def resend_invitation(invitation_id: UUID, request: Request, user: User = Depends(require_verified_user), _: object = Depends(require_csrf), context: OrganizationContext = Depends(require_organization_permission("organization.invitations.manage")), db: AsyncSession = Depends(get_db)) -> InvitationCreated:
    ensure_trusted_origin(request)
    invitation = await db.scalar(select(OrganizationInvitation).where(OrganizationInvitation.id == invitation_id, OrganizationInvitation.organization_id == context.organization.id).with_for_update())
    if invitation is None or invitation.accepted_at:
        raise HTTPException(status_code=404, detail="Invitation not found")
    token = generate_token()
    invitation.token_hash = hash_token(token)
    invitation.expires_at = utc_now() + timedelta(days=7)
    invitation.revoked_at = None
    invitation.declined_at = None
    await _audit(db, context, user.id, "invitation.resent", invitation.id)
    await db.commit()
    await db.refresh(invitation)
    exposed = token if get_settings().environment in {"development", "test"} else None
    return InvitationCreated(invitation=InvitationRead.model_validate(invitation), token=exposed)


@router.post("/{organization_id}/knowledge-bases", response_model=KnowledgeBaseRead, status_code=201)
async def create_knowledge_base(payload: KnowledgeBaseCreate, request: Request, user: User = Depends(require_verified_user), _: object = Depends(require_csrf), context: OrganizationContext = Depends(require_organization_permission("organization.knowledge.manage")), db: AsyncSession = Depends(get_db)) -> KnowledgeBaseRead:
    ensure_trusted_origin(request)
    normalized = payload.name.casefold()
    if await db.scalar(select(KnowledgeBase.id).where(KnowledgeBase.organization_id == context.organization.id, KnowledgeBase.normalized_name == normalized)):
        raise HTTPException(status_code=409, detail="Knowledge base name is already in use")
    item = KnowledgeBase(organization_id=context.organization.id, created_by=user.id, name=payload.name, normalized_name=normalized, description=payload.description)
    db.add(item)
    await _audit(db, context, user.id, "knowledge_base.created", item.id)
    await db.commit()
    await db.refresh(item)
    return KnowledgeBaseRead.model_validate(item)


@router.get("/{organization_id}/knowledge-bases", response_model=list[KnowledgeBaseRead])
async def list_knowledge_bases(context: OrganizationContext = Depends(require_organization_permission("organization.knowledge.read")), db: AsyncSession = Depends(get_db)) -> list[KnowledgeBaseRead]:
    rows = await db.scalars(select(KnowledgeBase).where(KnowledgeBase.organization_id == context.organization.id, KnowledgeBase.status == "active").order_by(KnowledgeBase.name.asc()))
    return [KnowledgeBaseRead.model_validate(item) for item in rows]


@invitation_router.post("/{token}/accept", response_model=OrganizationSummary)
async def accept_invitation(token: str, request: Request, user: User = Depends(require_verified_user), _: object = Depends(require_csrf), db: AsyncSession = Depends(get_db)) -> OrganizationSummary:
    ensure_trusted_origin(request)
    invitation = await db.scalar(select(OrganizationInvitation).where(OrganizationInvitation.token_hash == hash_token(token)).with_for_update())
    if invitation is None or invitation.accepted_at or invitation.revoked_at or invitation.expires_at <= utc_now():
        raise HTTPException(status_code=404, detail={"code": "INVITATION_INVALID", "message": "Invitation is invalid or expired"})
    if user.email_normalized != invitation.email_normalized:
        raise HTTPException(status_code=403, detail={"code": "INVITATION_EMAIL_MISMATCH", "message": "Invitation email does not match the signed-in account"})
    existing = await db.scalar(select(OrganizationMembership).where(OrganizationMembership.organization_id == invitation.organization_id, OrganizationMembership.user_id == user.id))
    if existing and existing.status == "active":
        raise HTTPException(status_code=409, detail="Membership already exists")
    if existing:
        existing.status = "active"
        existing.role = invitation.role
    else:
        db.add(OrganizationMembership(organization_id=invitation.organization_id, user_id=user.id, role=invitation.role, status="active"))
    invitation.accepted_at = utc_now()
    await db.commit()
    organization = await db.get(Organization, invitation.organization_id)
    return OrganizationSummary(id=organization.id, slug=organization.slug, name=organization.name, status=organization.status, role=invitation.role)


@invitation_router.post("/{token}/decline", status_code=204)
async def decline_invitation(token: str, request: Request, user: User = Depends(require_verified_user), _: object = Depends(require_csrf), db: AsyncSession = Depends(get_db)) -> None:
    ensure_trusted_origin(request)
    invitation = await db.scalar(select(OrganizationInvitation).where(OrganizationInvitation.token_hash == hash_token(token), OrganizationInvitation.email_normalized == user.email_normalized).with_for_update())
    if invitation is None or invitation.accepted_at or invitation.revoked_at or invitation.expires_at <= utc_now():
        raise HTTPException(status_code=404, detail={"code": "INVITATION_INVALID", "message": "Invitation is invalid or expired"})
    invitation.declined_at = utc_now()
    await db.commit()
