import asyncio
from types import SimpleNamespace

import pytest

from app.services import ai_provider


class Event:
    def __init__(self, event_type: str, delta: str = "", response=None):
        self.type = event_type
        self.delta = delta
        self.response = response


class FakeResponses:
    async def create(self, **_: object):
        async def events():
            yield Event("response.output_text.delta", "hello")
            yield Event("response.completed")

        return events()


class FakeClient:
    responses = FakeResponses()


@pytest.mark.asyncio
async def test_responses_stream_translates_text_events(monkeypatch):
    monkeypatch.setattr(ai_provider, "get_openai_client", lambda: FakeClient())
    events = [
        event
        async for event in ai_provider.stream_response(
            model="test", instructions="safe", input_items=[]
        )
    ]
    assert events[0].type == "response.output_text.delta"
    assert events[0].delta == "hello"
    assert events[-1].type == "response.completed"


@pytest.mark.asyncio
async def test_output_text_done_is_not_application_completion(monkeypatch):
    class Responses:
        async def create(self, **_: object):
            async def events():
                yield Event("response.output_text.delta", "မင်္ဂလာ")
                yield Event("response.output_text.done")
                yield Event("response.completed", response=SimpleNamespace(id="resp_1"))

            return events()

    monkeypatch.setattr(
        ai_provider, "get_openai_client", lambda: SimpleNamespace(responses=Responses())
    )
    events = [
        event
        async for event in ai_provider.stream_response(
            model="test", instructions="safe", input_items=[]
        )
    ]
    assert [event.type for event in events] == [
        "response.output_text.delta",
        "response.completed",
    ]
    assert events[0].delta == "မင်္ဂလာ"


@pytest.mark.asyncio
async def test_quiet_provider_emits_heartbeat_before_deadline(monkeypatch):
    class Responses:
        async def create(self, **_: object):
            async def events():
                await asyncio.sleep(0.02)
                yield Event("response.completed")

            return events()

    monkeypatch.setattr(
        ai_provider, "get_openai_client", lambda: SimpleNamespace(responses=Responses())
    )
    monkeypatch.setattr(
        ai_provider,
        "get_settings",
        lambda: SimpleNamespace(
            ai_timeout_seconds=0.1, ai_max_output_tokens=10, openai_api_key="test"
        ),
    )
    monkeypatch.setattr(ai_provider, "STREAM_HEARTBEAT_SECONDS", 0.01)
    events = [
        event
        async for event in ai_provider.stream_response(
            model="test", instructions="safe", input_items=[]
        )
    ]
    assert events[-1].type == "response.completed"
    assert any(event.type == "heartbeat" for event in events)


@pytest.mark.asyncio
async def test_provider_incomplete_event_is_preserved(monkeypatch):
    class Responses:
        async def create(self, **_: object):
            async def events():
                yield Event("response.output_text.delta", "partial")
                yield Event("response.incomplete")

            return events()

    monkeypatch.setattr(
        ai_provider, "get_openai_client", lambda: SimpleNamespace(responses=Responses())
    )
    events = [
        event
        async for event in ai_provider.stream_response(
            model="test", instructions="safe", input_items=[]
        )
    ]
    assert [event.type for event in events] == [
        "response.output_text.delta",
        "response.incomplete",
    ]


@pytest.mark.asyncio
async def test_provider_timeout_is_translated(monkeypatch):
    class Responses:
        async def create(self, **_: object):
            async def events():
                await asyncio.sleep(0.05)
                yield Event("response.completed")

            return events()

    monkeypatch.setattr(
        ai_provider, "get_openai_client", lambda: SimpleNamespace(responses=Responses())
    )
    monkeypatch.setattr(
        ai_provider,
        "get_settings",
        lambda: SimpleNamespace(
            ai_timeout_seconds=0.01, ai_max_output_tokens=10, openai_api_key="test"
        ),
    )
    monkeypatch.setattr(ai_provider, "STREAM_HEARTBEAT_SECONDS", 0.1)
    with pytest.raises(ai_provider.ProviderRequestError, match="AI_PROVIDER_TIMEOUT"):
        async for _ in ai_provider.stream_response(
            model="test", instructions="safe", input_items=[]
        ):
            pass
