from typing import Any

from app.models.schemas import ConversationMessage


def normalize_message_text(message: ConversationMessage | str) -> str:
    content = message if isinstance(message, str) else message.content
    return " ".join(content.split()).strip()


def parse_conversation_messages(
    raw_payload: dict[str, Any],
) -> list[ConversationMessage]:
    raw_messages = raw_payload.get("messages", [])
    if not isinstance(raw_messages, list):
        return []
    return [ConversationMessage.model_validate(item) for item in raw_messages]


def analysis_text_for_message(
    message: ConversationMessage,
    previous_assistant_context: str | None = None,
) -> str:
    normalized = normalize_message_text(message)
    if message.role == "user" and previous_assistant_context:
        return normalize_message_text(f"{previous_assistant_context} {normalized}")
    return normalized
