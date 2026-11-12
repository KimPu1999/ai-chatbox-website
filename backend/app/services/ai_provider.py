import asyncio
import inspect
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from app.core.config import get_settings


class ProviderUnavailable(Exception):
    code = "AI_PROVIDER_UNAVAILABLE"


class ProviderRequestError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass
class ProviderEvent:
    type: str
    delta: str = ""
    response: Any = None
    error: Any = None


_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    global _client
    settings = get_settings()
    if not settings.openai_api_key:
        raise ProviderUnavailable("OpenAI API key is not configured")
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.ai_timeout_seconds,
            max_retries=2,
        )
    return _client


async def close_openai_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None


def configured_models() -> tuple[str, ...]:
    return get_settings().allowed_ai_models


def validate_model(model: str | None) -> str:
    selected = model or get_settings().openai_model
    if selected not in configured_models():
        raise ProviderRequestError("AI_MODEL_NOT_ALLOWED")
    return selected


async def stream_response(
    *, model: str, instructions: str, input_items: list[dict[str, str]]
) -> AsyncIterator[ProviderEvent]:
    stream = None
    try:
        stream = await get_openai_client().responses.create(
            model=model,
            instructions=instructions,
            input=input_items,
            stream=True,
            store=False,
            max_output_tokens=get_settings().ai_max_output_tokens,
        )
        async with asyncio.timeout(get_settings().ai_timeout_seconds):
            async for event in stream:
                event_type = getattr(event, "type", "")
                if event_type == "response.output_text.delta":
                    yield ProviderEvent(type=event_type, delta=getattr(event, "delta", ""))
                elif event_type in {"response.completed", "response.failed", "response.incomplete"}:
                    yield ProviderEvent(
                        type=event_type,
                        response=getattr(event, "response", None),
                        error=getattr(event, "response", None),
                    )
                elif event_type == "error":
                    yield ProviderEvent(type=event_type, error=event)
    except TimeoutError as exc:
        raise ProviderRequestError("AI_PROVIDER_TIMEOUT") from exc
    except (APITimeoutError, APIConnectionError) as exc:
        raise ProviderRequestError("AI_PROVIDER_TIMEOUT") from exc
    except APIStatusError as exc:
        if exc.status_code == 429:
            raise ProviderRequestError("AI_PROVIDER_RATE_LIMITED") from exc
        if exc.status_code >= 500:
            raise ProviderRequestError("AI_PROVIDER_UNAVAILABLE") from exc
        raise ProviderRequestError("AI_PROVIDER_REQUEST_FAILED") from exc
    finally:
        if stream is not None and hasattr(stream, "close"):
            result = stream.close()
            if inspect.isawaitable(result):
                await result
