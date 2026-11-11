"""ARQ worker entrypoint for durable document processing.

Run with ``arq app.worker.WorkerSettings`` after setting REDIS_URL. The API
keeps the job row in PostgreSQL so stale or failed jobs remain inspectable.
"""

from arq.connections import RedisSettings

from app.core.config import get_settings
from app.services.documents import process_document_by_id


async def process_document(_ctx: dict, document_id: str) -> None:
    from uuid import UUID

    await process_document_by_id(UUID(document_id))


class WorkerSettings:
    functions = [process_document]
    max_jobs = 2
    job_timeout = get_settings().document_processing_timeout_seconds

    @staticmethod
    def redis_settings() -> RedisSettings:
        settings = get_settings()
        if not settings.redis_url:
            raise RuntimeError("REDIS_URL is required to run the durable document worker")
        return RedisSettings.from_dsn(settings.redis_url)
