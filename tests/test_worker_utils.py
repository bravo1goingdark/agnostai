from uuid import uuid4

from app.models.schemas import ConversationMessage
from app.models.tables import Conversation
from app.services.embeddings import embed_text_stub, embedding_metadata
from app.services.normalization import (
    analysis_text_for_message,
    normalize_message_text,
    parse_conversation_messages,
)
from app.services.pii import redact_obvious_pii
from app.services.sentiment import score_sentiment_stub
from app.workers.jobs import _load_existing_embedding_message_ids, prepare_message_rows


def test_normalization_and_redaction_helpers() -> None:
    message = ConversationMessage(
        role="user",
        content="  Email me at user@example.com and call 555-222-1111  ",
    )

    normalized = normalize_message_text(message)
    redacted = redact_obvious_pii(normalized)

    assert normalized == "Email me at user@example.com and call 555-222-1111"
    assert "[REDACTED_EMAIL]" in redacted
    assert "[REDACTED_PHONE]" in redacted


def test_parse_conversation_messages_and_context() -> None:
    raw_payload = {
        "messages": [
            {"role": "assistant", "content": "Try the setup step again."},
            {"role": "user", "content": "It still fails."},
        ]
    }

    messages = parse_conversation_messages(raw_payload)
    assert len(messages) == 2
    assert analysis_text_for_message(messages[1], "Try the setup step again.") == (
        "Try the setup step again. It still fails."
    )


def test_sentiment_and_embedding_helpers() -> None:
    score, label = score_sentiment_stub("This is blocked and bad")
    metadata = embedding_metadata()
    vector = embed_text_stub("hello", int(metadata["dimension"]))

    assert label == "negative"
    assert score < 0
    assert len(vector) == int(metadata["dimension"])
    assert 0.0 <= vector[0] <= 1.0


def test_prepare_message_rows_creates_analysis_rows() -> None:
    conversation = Conversation(
        id=uuid4(),
        project_id="project-1",
        external_id="conversation-1",
        content_hash="hash",
        raw_payload={
            "messages": [
                {"message_id": "m1", "role": "assistant", "content": "Try again."},
                {
                    "message_id": "m2",
                    "role": "user",
                    "content": "It is broken.",
                },
            ]
        },
        metadata_={"source": "test"},
    )

    rows = prepare_message_rows(conversation)

    assert len(rows) == 2
    assert rows[1].content == "Try again. It is broken."
    assert rows[1].role == "user"


def test_worker_embedding_id_loader_handles_empty_input() -> None:
    async def _run() -> set[str]:
        class _Session:
            async def execute(self, *args, **kwargs):  # type: ignore[no-untyped-def]
                raise AssertionError("should not be called")

        result = await _load_existing_embedding_message_ids(
            _Session(),
            "project-1",
            [],
            "model",
        )
        return {str(item) for item in result}

    import asyncio

    assert asyncio.run(_run()) == set()
