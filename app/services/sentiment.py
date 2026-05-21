from typing import Literal

SentimentLabel = Literal["negative", "neutral", "positive"]


def score_sentiment_stub(text: str) -> tuple[float, SentimentLabel]:
    """Cheap deterministic placeholder until the Phase 3 scorer is wired."""
    lowered = text.lower()
    if any(token in lowered for token in ("broken", "blocked", "angry", "bad")):
        return -0.5, "negative"
    if any(token in lowered for token in ("great", "thanks", "love", "good")):
        return 0.5, "positive"
    return 0.0, "neutral"


def is_user_message(role: str) -> bool:
    return role == "user"
