import pytest

from app.services import ai_provider


class Event:
    def __init__(self, event_type: str, delta: str = ""):
        self.type = event_type
        self.delta = delta


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
