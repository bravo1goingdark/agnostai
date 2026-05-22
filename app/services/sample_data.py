from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import ConversationIngestRequest
from app.services.ingestion import enqueue_conversation_ingest
from app.workers.jobs import process_conversation


@dataclass(slots=True)
class SampleSeedResult:
    project_id: str
    accepted: int = 0
    duplicate: int = 0
    processed: int = 0
    stored_conversation_ids: list[str] = field(default_factory=list)


def sample_payloads(
    project_id: str,
    *,
    now: datetime | None = None,
) -> list[ConversationIngestRequest]:
    base_time = now or datetime.now(UTC)
    themes = [
        (
            "setup",
            [
                "Setup wizard keeps failing on the API key step and onboarding stalls.",
                "Onboarding flow rejects our API key during initial workspace setup.",
                "API key validation errors stop the setup wizard from completing.",
            ],
            "Ask for the exact onboarding error and confirm the API key scopes.",
        ),
        (
            "billing",
            [
                "Billing invoice sync stopped working after the plan upgrade.",
                "Finance team cannot reconcile invoices since billing sync broke.",
                "Invoice totals mismatch after upgrade and billing reports are wrong.",
            ],
            "Escalate the invoice sync failure and capture the billing account id.",
        ),
        (
            "report",
            [
                "Report export to CSV is missing from the dashboard download menu.",
                "Dashboard CSV export button does nothing for weekly product review.",
                "Cannot export topic reports to CSV from the analytics dashboard.",
            ],
            "Confirm the report export filters and share the dashboard workspace.",
        ),
    ]
    payloads: list[ConversationIngestRequest] = []
    for theme_index, (theme, user_messages, assistant_template) in enumerate(themes):
        for item_index, user_message in enumerate(user_messages):
            created_at = base_time - timedelta(hours=(theme_index * 8) + item_index)
            payloads.append(
                ConversationIngestRequest(
                    project_id=project_id,
                    conversation_id=f"sample-{theme}-{item_index + 1}",
                    messages=[
                        {
                            "role": "user",
                            "content": user_message,
                            "created_at": created_at,
                            "metadata": {"sample_theme": theme},
                        },
                        {
                            "role": "assistant",
                            "content": assistant_template,
                            "created_at": created_at + timedelta(minutes=4),
                            "metadata": {"sample_theme": theme},
                        },
                    ],
                    metadata={"source": "sample", "theme": theme},
                )
            )
    return payloads


async def seed_sample_conversations(
    session: AsyncSession,
    project_id: str,
    *,
    process_inline: bool = True,
) -> SampleSeedResult:
    result = SampleSeedResult(project_id=project_id)
    for payload in sample_payloads(project_id):
        response = await enqueue_conversation_ingest(
            payload,
            session,
            queue_factory=_queue_factory,
        )
        if response.status == "accepted":
            result.accepted += 1
        else:
            result.duplicate += 1
        if response.stored_conversation_id is None:
            continue
        result.stored_conversation_ids.append(response.stored_conversation_id)
        if response.status == "accepted" and process_inline:
            await process_conversation(
                {"session": session},
                project_id,
                response.stored_conversation_id,
            )
            result.processed += 1
    return result


class _NullQueue:
    async def enqueue_job(self, *args: object, **kwargs: object) -> object:
        class _Job:
            job_id = "sample-inline-job"

        return _Job()

    async def aclose(self) -> None:
        return None


async def _queue_factory() -> _NullQueue:
    return _NullQueue()
