from datetime import datetime, timezone
from uuid import uuid4

from app.schemas import BulkActionRequest, FolderCreate, ShareCreate
from app.services.advanced_conversations import _decode_cursor, _encode_cursor


def test_conversation_cursor_round_trip_is_url_safe() -> None:
    value = {"pinned": 1, "timestamp": datetime.now(timezone.utc).isoformat(), "id": str(uuid4())}
    encoded = _encode_cursor(value)
    assert "+" not in encoded
    assert _decode_cursor(encoded) == value


def test_folder_and_share_validation() -> None:
    assert FolderCreate(name="  Burmese စကားဝိုင်း  ").name == "Burmese စကားဝိုင်း"
    assert ShareCreate(expires_in_days=7, password="secure123").password == "secure123"


def test_bulk_action_rejects_duplicate_ids() -> None:
    conversation_id = uuid4()
    try:
        BulkActionRequest(
            conversation_ids=[conversation_id, conversation_id], action="archive"
        )
    except ValueError as exc:
        assert "unique" in str(exc).lower()
    else:
        raise AssertionError("duplicate bulk IDs were accepted")
