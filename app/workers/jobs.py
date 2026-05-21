import logging

logger = logging.getLogger(__name__)


async def process_conversation(
    ctx: dict[str, object],
    project_id: str,
    conversation_id: str,
) -> None:
    _ = ctx
    logger.info(
        "process_conversation_stub project_id=%s conversation_id=%s",
        project_id,
        conversation_id,
    )
