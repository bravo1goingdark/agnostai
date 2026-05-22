from __future__ import annotations

import importlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import sqrt
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.tables import (
    ClusterRun,
    Message,
    MessageEmbedding,
    Topic,
    TopicMembership,
)

try:  # pragma: no cover - optional dependency path
    hdbscan: Any | None = importlib.import_module("hdbscan")
except Exception:  # pragma: no cover - optional dependency path
    hdbscan = None

try:  # pragma: no cover - optional dependency path
    np: Any | None = importlib.import_module("numpy")
except Exception:  # pragma: no cover - optional dependency path
    np = None

STOPWORDS = {
    "about",
    "after",
    "again",
    "also",
    "and",
    "around",
    "because",
    "been",
    "before",
    "blocked",
    "broken",
    "cant",
    "could",
    "during",
    "failing",
    "from",
    "have",
    "into",
    "just",
    "keeps",
    "need",
    "please",
    "still",
    "that",
    "the",
    "this",
    "through",
    "with",
    "would",
}


@dataclass(slots=True)
class MessageCluster:
    cluster_label: int
    message_ids: list[UUID]
    texts: list[str]
    embeddings: list[list[float]]
    created_at_values: list[datetime | None]
    sentiment_scores: list[float | None]
    sentiment_labels: list[str | None]
    conversation_ids: list[UUID]
    representative_message_id: UUID | None = None
    terms: list[str] | None = None
    label: str | None = None
    summary: str | None = None


@dataclass(slots=True)
class TopicRunResult:
    cluster_run: ClusterRun
    topics: list[Topic]
    memberships: list[TopicMembership]


def clustering_not_ready() -> dict[str, str]:
    return {"status": "not_ready"}


async def run_cluster_batch(
    session: AsyncSession,
    project_id: str,
    *,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    parameters: dict[str, Any] | None = None,
) -> TopicRunResult:
    settings = get_settings()
    params = {
        "min_cluster_size": settings.clustering_min_cluster_size,
        "model_name": settings.embedding_model_name,
        **(parameters or {}),
    }
    run = ClusterRun(
        project_id=project_id,
        status="running",
        window_start=window_start,
        window_end=window_end,
        parameters=params,
    )
    session.add(run)
    await session.flush()
    await session.commit()

    try:
        messages = await _load_cluster_candidates(
            session,
            project_id,
            window_start=window_start,
            window_end=window_end,
        )
        clusters = _cluster_messages(
            messages, min_cluster_size=params["min_cluster_size"]
        )
        topics = _build_topics(run.id, project_id, clusters, messages)
        await _replace_previous_topics(session, project_id)
        session.add_all(topics)
        await session.flush()
        memberships = _build_memberships(topics, clusters, messages)
        session.add_all(memberships)
        run.status = "completed"
        run.completed_at = datetime.now(UTC)
        await session.commit()
        return TopicRunResult(cluster_run=run, topics=topics, memberships=memberships)
    except Exception as exc:
        await session.rollback()
        failed_run = await session.get(ClusterRun, run.id)
        if failed_run is not None:
            failed_run.status = "failed"
            failed_run.error_message = str(exc)
            failed_run.completed_at = datetime.now(UTC)
            await session.commit()
        raise


async def latest_cluster_run(
    session: AsyncSession, project_id: str
) -> ClusterRun | None:
    result = await session.execute(
        select(ClusterRun)
        .where(ClusterRun.project_id == project_id)
        .order_by(ClusterRun.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def load_topics(
    session: AsyncSession,
    project_id: str,
    cluster_run_id: UUID | None = None,
) -> list[Topic]:
    query = select(Topic).where(Topic.project_id == project_id)
    if cluster_run_id is not None:
        query = query.where(Topic.cluster_run_id == cluster_run_id)
    query = query.order_by(Topic.member_count.desc(), Topic.created_at.asc())
    result = await session.execute(query)
    return list(result.scalars().all())


async def load_topic_detail(
    session: AsyncSession,
    topic_id: UUID,
) -> tuple[Topic | None, list[TopicMembership], list[Message]]:
    topic = await session.get(Topic, topic_id)
    if topic is None:
        return None, [], []

    memberships_result = await session.execute(
        select(TopicMembership)
        .where(TopicMembership.topic_id == topic_id)
        .order_by(
            TopicMembership.is_representative.desc(), TopicMembership.created_at.asc()
        )
    )
    memberships = list(memberships_result.scalars().all())
    message_ids = [membership.message_id for membership in memberships]
    if not message_ids:
        return topic, memberships, []

    messages_result = await session.execute(
        select(Message).where(Message.id.in_(message_ids))
    )
    messages_by_id = {
        message.id: message for message in messages_result.scalars().all()
    }
    ordered_messages = [
        messages_by_id[message_id]
        for message_id in message_ids
        if message_id in messages_by_id
    ]
    return topic, memberships, ordered_messages


async def compute_insights(
    session: AsyncSession,
    project_id: str,
) -> dict[str, Any]:
    run = await latest_cluster_run(session, project_id)
    topics = await load_topics(session, project_id, run.id if run is not None else None)
    sentiment_rows = await session.execute(
        select(Message.sentiment_label, func.count())
        .where(Message.project_id == project_id)
        .group_by(Message.sentiment_label)
    )
    sentiment_distribution: dict[str, int] = {}
    for sentiment_label, count in sentiment_rows.all():
        sentiment_distribution[sentiment_label or "unknown"] = int(count)

    total_messages_result = await session.execute(
        select(func.count())
        .select_from(Message)
        .where(Message.project_id == project_id)
    )
    total_messages = int(total_messages_result.scalar_one() or 0)

    return {
        "project_id": project_id,
        "latest_cluster_run_id": str(run.id) if run is not None else None,
        "generated_at": datetime.now(UTC),
        "total_messages": total_messages,
        "total_topics": len(topics),
        "top_topics": [topic_to_summary(topic) for topic in topics[:5]],
        "sentiment_distribution": sentiment_distribution,
        "emerging_topics": [
            topic_to_summary(topic) for topic in topics if (topic.growth_24h or 0) > 0
        ][:5],
    }


async def _load_cluster_candidates(
    session: AsyncSession,
    project_id: str,
    *,
    window_start: datetime | None,
    window_end: datetime | None,
) -> list[dict[str, Any]]:
    query = (
        select(
            Message.id,
            Message.conversation_id,
            Message.content,
            Message.sentiment_score,
            Message.sentiment_label,
            Message.created_at,
            MessageEmbedding.embedding,
        )
        .join(MessageEmbedding, MessageEmbedding.message_id == Message.id)
        .where(Message.project_id == project_id)
        .where(Message.role == "user")
        .order_by(Message.created_at.asc().nulls_last(), Message.sequence_index.asc())
    )
    if window_start is not None:
        query = query.where(
            Message.created_at.is_(None) | (Message.created_at >= window_start)
        )
    if window_end is not None:
        query = query.where(
            Message.created_at.is_(None) | (Message.created_at <= window_end)
        )

    result = await session.execute(query)
    rows: list[dict[str, Any]] = []
    for row in result.all():
        rows.append(
            {
                "message_id": row.id,
                "conversation_id": row.conversation_id,
                "content": row.content,
                "sentiment_score": row.sentiment_score,
                "sentiment_label": row.sentiment_label,
                "created_at": row.created_at,
                "embedding": _coerce_embedding(row.embedding),
            }
        )
    return rows


def _cluster_messages(
    messages: list[dict[str, Any]],
    *,
    min_cluster_size: int,
) -> list[MessageCluster]:
    if not messages:
        return []

    labels = _fallback_labels(messages, min_cluster_size=min_cluster_size)
    if (
        hdbscan is not None
        and np is not None
        and len(messages) >= max(min_cluster_size, 2)
    ):
        embeddings = np.asarray(
            [message["embedding"] for message in messages], dtype=np.float32
        )
        labels = (
            hdbscan.HDBSCAN(
                min_cluster_size=max(2, min_cluster_size),
                metric="euclidean",
                prediction_data=False,
            )
            .fit_predict(embeddings)
            .tolist()
        )

    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    noise_label = (
        max([int(label) for label in labels if int(label) >= 0], default=-1) + 1
    )
    for message, label in zip(messages, labels, strict=False):
        cluster_label = int(label)
        if cluster_label == -1:
            cluster_label = noise_label
            noise_label += 1
        grouped[cluster_label].append(message)

    return [
        _build_cluster(cluster_label, cluster_messages)
        for cluster_label, cluster_messages in sorted(grouped.items())
    ]


def _fallback_labels(
    messages: list[dict[str, Any]], *, min_cluster_size: int
) -> list[int]:
    token_counts: Counter[str] = Counter()
    message_tokens: list[list[str]] = []
    for message in messages:
        tokens = [
            token
            for token in _significant_tokens(message["content"])
            if len(token) >= 4
        ]
        message_tokens.append(tokens)
        token_counts.update(set(tokens))

    total = len(messages)
    df_ceiling = max(2, int(total * 0.6)) if total >= 4 else total

    buckets: dict[tuple[str, ...], int] = {}
    labels: list[int] = []
    next_label = 0
    signature_size = max(1, min_cluster_size // 2 or 1)
    for tokens in message_tokens:
        ranked = sorted(
            [
                token
                for token in tokens
                if 2 <= token_counts[token] <= df_ceiling
            ],
            key=lambda token: (-token_counts[token], token),
        )
        if not ranked:
            labels.append(-1)
            continue
        signature = tuple(ranked[:signature_size])
        if signature not in buckets:
            buckets[signature] = next_label
            next_label += 1
        labels.append(buckets[signature])
    return labels


def _build_cluster(
    cluster_label: int,
    cluster_messages: list[dict[str, Any]],
) -> MessageCluster:
    representative = _choose_representative_message(cluster_messages)
    texts = [message["content"] for message in cluster_messages]
    cluster = MessageCluster(
        cluster_label=cluster_label,
        message_ids=[message["message_id"] for message in cluster_messages],
        texts=texts,
        embeddings=[message["embedding"] for message in cluster_messages],
        created_at_values=[message["created_at"] for message in cluster_messages],
        sentiment_scores=[message["sentiment_score"] for message in cluster_messages],
        sentiment_labels=[message["sentiment_label"] for message in cluster_messages],
        conversation_ids=[message["conversation_id"] for message in cluster_messages],
        representative_message_id=representative["message_id"]
        if representative
        else None,
    )
    cluster.terms = _extract_terms(texts)
    cluster.label = _generate_topic_label(
        cluster_label,
        cluster.terms,
        representative["content"] if representative else None,
    )
    cluster.summary = _generate_topic_summary(cluster.terms, texts)
    return cluster


def _choose_representative_message(
    cluster_messages: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not cluster_messages:
        return None
    return max(
        cluster_messages,
        key=lambda message: (
            float(message.get("sentiment_score") or 0.0),
            len(message.get("content") or ""),
            _ensure_aware_datetime(message.get("created_at"))
            or datetime.min.replace(tzinfo=UTC),
        ),
    )


def _extract_terms(texts: list[str]) -> list[str]:
    counter: Counter[str] = Counter()
    for text in texts:
        for token in _significant_tokens(text):
            if len(token) >= 4:
                counter[token] += 1
    return [term for term, _ in counter.most_common(8)]


def _generate_topic_label(
    cluster_label: int,
    terms: list[str],
    representative_text: str | None,
) -> str:
    if terms:
        return " / ".join(terms[:3])
    if representative_text:
        return representative_text[:80]
    return f"topic-{cluster_label}"


def _generate_topic_summary(terms: list[str], texts: list[str]) -> str:
    if texts:
        first_sentence = texts[0].split(".")[0].strip()
        if first_sentence:
            return first_sentence[:160]
    if terms:
        return f"Recurring theme around {', '.join(terms[:3])}."
    return "Clustered conversation theme."


def _build_topics(
    cluster_run_id: UUID,
    project_id: str,
    clusters: list[MessageCluster],
    messages: list[dict[str, Any]],
) -> list[Topic]:
    message_lookup = {message["message_id"]: message for message in messages}
    topics: list[Topic] = []

    for cluster in clusters:
        cluster_messages = [
            message_lookup[message_id]
            for message_id in cluster.message_ids
            if message_id in message_lookup
        ]
        if not cluster_messages:
            continue

        topic = Topic(
            project_id=project_id,
            cluster_run_id=cluster_run_id,
            cluster_label=cluster.cluster_label,
            label=cluster.label or f"topic-{cluster.cluster_label}",
            summary=cluster.summary,
            terms=cluster.terms or [],
            member_count=len(cluster_messages),
            growth_24h=_growth_rate(cluster_messages, hours=24),
            growth_7d=_growth_rate(cluster_messages, hours=24 * 7),
            sentiment_mean=_mean(
                [message.get("sentiment_score") for message in cluster_messages]
            ),
            negative_sentiment_share=_negative_share(cluster_messages),
            first_seen_at=_min_datetime(
                [message.get("created_at") for message in cluster_messages]
            ),
            last_seen_at=_max_datetime(
                [message.get("created_at") for message in cluster_messages]
            ),
        )
        topics.append(topic)
    return topics


def _build_memberships(
    topics: list[Topic],
    clusters: list[MessageCluster],
    messages: list[dict[str, Any]],
) -> list[TopicMembership]:
    message_lookup = {message["message_id"]: message for message in messages}
    topic_lookup = {topic.cluster_label: topic for topic in topics}
    memberships: list[TopicMembership] = []

    for cluster in clusters:
        topic = topic_lookup.get(cluster.cluster_label)
        if topic is None:
            continue
        cluster_messages = [
            message_lookup[message_id]
            for message_id in cluster.message_ids
            if message_id in message_lookup
        ]
        if not cluster_messages:
            continue
        representative_message_id = (
            cluster.representative_message_id or cluster.message_ids[0]
        )
        for index, message in enumerate(cluster_messages):
            memberships.append(
                TopicMembership(
                    project_id=topic.project_id,
                    topic_id=topic.id,
                    message_id=message["message_id"],
                    similarity=_similarity(cluster, message["embedding"]),
                    is_representative=message["message_id"] == representative_message_id
                    or index == 0,
                )
            )
    return memberships


async def _replace_previous_topics(session: AsyncSession, project_id: str) -> None:
    await session.execute(
        delete(TopicMembership).where(TopicMembership.project_id == project_id)
    )
    await session.execute(delete(Topic).where(Topic.project_id == project_id))


def _similarity(cluster: MessageCluster, embedding: list[float]) -> float:
    if not cluster.embeddings:
        return 0.0
    cluster_vector = [
        sum(values) / len(values) for values in zip(*cluster.embeddings, strict=False)
    ]
    denom = _vector_norm(cluster_vector) * _vector_norm(embedding)
    if denom == 0.0:
        return 0.0
    dot_product = sum(
        left * right for left, right in zip(cluster_vector, embedding, strict=False)
    )
    return float(max(-1.0, min(1.0, dot_product / denom)))


def _mean(values: list[float | None]) -> float | None:
    numeric = [value for value in values if value is not None]
    if not numeric:
        return None
    return float(sum(numeric) / len(numeric))


def _negative_share(messages: list[dict[str, Any]]) -> float | None:
    total = 0
    negative = 0
    for message in messages:
        label = message.get("sentiment_label")
        if label is None:
            continue
        total += 1
        if label == "negative":
            negative += 1
    if total == 0:
        return None
    return negative / total


def _min_datetime(values: list[datetime | None]) -> datetime | None:
    items = [value for value in values if value is not None]
    if not items:
        return None
    return min(items)


def _max_datetime(values: list[datetime | None]) -> datetime | None:
    items = [value for value in values if value is not None]
    if not items:
        return None
    return max(items)


def _growth_rate(messages: list[dict[str, Any]], *, hours: int) -> float | None:
    if len(messages) < 2:
        return None
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    recent = 0
    older = 0
    for message in messages:
        created_at = _ensure_aware_datetime(message.get("created_at"))
        if created_at is None or created_at < cutoff:
            continue
        if created_at >= cutoff + timedelta(hours=hours / 2):
            recent += 1
        else:
            older += 1
    if older == 0:
        return float(recent) if recent else None
    return (recent - older) / older


def _tokenize(text: str) -> list[str]:
    return [
        token.lower().strip(".,:;!?()[]{}<>\"'")
        for token in text.split()
        if token.strip()
    ]


def _significant_tokens(text: str) -> list[str]:
    return [token for token in _tokenize(text) if token and token not in STOPWORDS]


def _ensure_aware_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _coerce_embedding(value: Any) -> list[float]:
    if np is not None and isinstance(value, np.ndarray):
        return [float(item) for item in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [float(item) for item in value]
    try:
        return [float(item) for item in list(value)]
    except TypeError:
        return [float(value)]


def _vector_norm(vector: list[float]) -> float:
    return sqrt(sum(value * value for value in vector))


def topic_to_summary(topic: Topic) -> dict[str, Any]:
    representative_examples = list(topic.terms or [])[:3]
    return {
        "id": str(topic.id),
        "cluster_run_id": str(topic.cluster_run_id),
        "cluster_label": topic.cluster_label,
        "label": topic.label,
        "summary": topic.summary,
        "terms": list(topic.terms or []),
        "member_count": topic.member_count,
        "growth_24h": topic.growth_24h,
        "growth_7d": topic.growth_7d,
        "sentiment_mean": topic.sentiment_mean,
        "negative_sentiment_share": topic.negative_sentiment_share,
        "first_seen_at": topic.first_seen_at,
        "last_seen_at": topic.last_seen_at,
        "representative_examples": representative_examples,
    }
