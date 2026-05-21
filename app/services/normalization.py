from app.models.schemas import ConversationMessage


def normalize_message_text(message: ConversationMessage) -> str:
    return " ".join(message.content.split())

