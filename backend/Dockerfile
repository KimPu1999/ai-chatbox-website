FROM python:3.11.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates curl libmagic1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 pychat \
    && useradd --system --uid 10001 --gid pychat --home-dir /app --shell /usr/sbin/nologin pychat

COPY backend/requirements.runtime.lock ./requirements.txt
RUN python -m pip install --upgrade "pip==25.3" \
    && python -m pip install -r requirements.txt

COPY backend/app ./app
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./alembic.ini

RUN mkdir -p /data/private \
    && chown -R pychat:pychat /app /data/private

USER pychat
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:${PORT:-8000}/health || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
