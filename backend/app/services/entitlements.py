"""Central plan, feature-flag and quota evaluation.

This module is deliberately server-only. Client payloads never influence a
user's plan, subscription status or quota values.
"""

import hashlib
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import FeatureFlag, Plan, PlanEntitlement, Subscription, UserQuotaOverride


def entitlement_error(code: str, message: str, status_code: int = 403) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


async def current_plan(db: AsyncSession, user_id: UUID) -> Plan | None:
    return await db.scalar(
        select(Plan)
        .join(Subscription, Subscription.plan_id == Plan.id)
        .where(
            Subscription.user_id == user_id,
            Subscription.status.in_(["active", "trialing"]),
            Plan.enabled.is_(True),
        )
        .order_by(Subscription.updated_at.desc())
    )


async def plan_entitlements(db: AsyncSession, plan_id: UUID | None) -> dict[str, dict]:
    if plan_id is None:
        return {}
    rows = await db.scalars(select(PlanEntitlement).where(PlanEntitlement.plan_id == plan_id))
    return {row.feature: row.value for row in rows}


async def get_entitlement_context(db: AsyncSession, user_id: UUID) -> dict:
    plan = await current_plan(db, user_id)
    values = await plan_entitlements(db, plan.id if plan else None)
    override = await db.get(UserQuotaOverride, user_id)
    limits = dict(values.get("limits", {}))
    if override:
        limits.update({key: value for key, value in override.limits.items() if value is not None})
    return {"plan": plan, "entitlements": values, "limits": limits}


async def require_feature(db: AsyncSession, user_id: UUID, feature: str) -> dict:
    context = await get_entitlement_context(db, user_id)
    value = context["entitlements"].get(feature)
    if not value or value.get("enabled", True) is False:
        raise entitlement_error(
            "FEATURE_NOT_INCLUDED", "This feature is not available on your plan"
        )
    return value


async def model_allowed(db: AsyncSession, user_id: UUID, model: str) -> bool:
    context = await get_entitlement_context(db, user_id)
    allowed = context["entitlements"].get("allowed_models", {}).get("models")
    return not allowed or model in allowed


async def evaluate_feature_flag(
    db: AsyncSession,
    key: str,
    user_id: UUID,
    *,
    role: str,
    plan_code: str | None,
) -> bool:
    flag = await db.scalar(select(FeatureFlag).where(FeatureFlag.key == key))
    if flag is None or not flag.enabled:
        return False
    if flag.admin_only and role not in {"admin", "superadmin"}:
        return False
    if str(user_id) in (flag.user_allowlist or []):
        return True
    if flag.plan_codes and (plan_code not in flag.plan_codes):
        return False
    bucket = int(hashlib.sha256(f"{key}:{user_id}".encode()).hexdigest()[:8], 16) % 100
    return bucket < flag.rollout_percent


def platform_safety_caps() -> dict[str, int]:
    settings = get_settings()
    return {
        "daily_token_limit": settings.ai_daily_token_budget,
        "concurrent_generation_limit": settings.ai_max_concurrent_generations,
        "requests_per_minute": settings.ai_max_requests_per_minute,
    }
