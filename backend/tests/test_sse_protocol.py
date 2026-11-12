import json

from app.api.v1.router import _sse


def test_sse_frame_has_id_event_json_and_blank_line_terminator() -> None:
    frame = _sse("message.delta", {"delta": "မင်္ဂလာ"}, "run:delta:1")

    assert frame.endswith("\n\n")
    assert "id: run:delta:1\n" in frame
    assert "event: message.delta\n" in frame
    payload = frame.split("data: ", 1)[1].split("\n", 1)[0]
    assert json.loads(payload) == {"delta": "မင်္ဂလာ"}
