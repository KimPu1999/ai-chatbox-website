from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def set_transaction_organization(db: AsyncSession, organization_id: UUID) -> None:
    """Set tenant context only for the current transaction on a pooled connection."""
    await db.execute(
        text("SELECT set_config('app.current_organization_id', :organization_id, true)"),
        {"organization_id": str(organization_id)},
    )
