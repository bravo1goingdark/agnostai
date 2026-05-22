from typing import Literal

SentimentLabel = Literal["negative", "neutral", "positive"]

_vader_analyzer: object | None = None


def _get_vader() -> object | None:
    global _vader_analyzer
    if _vader_analyzer is None:
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

            _vader_analyzer = SentimentIntensityAnalyzer()
        except Exception:
            _vader_analyzer = False
    return _vader_analyzer if _vader_analyzer is not False else None


def score_sentiment(text: str) -> tuple[float, SentimentLabel]:
    analyzer = _get_vader()
    if analyzer is not None:
        scores = analyzer.polarity_scores(text)  # type: ignore[attr-defined]
        compound = float(scores["compound"])
        if compound >= 0.05:
            return compound, "positive"
        elif compound <= -0.05:
            return compound, "negative"
        return compound, "neutral"
    return score_sentiment_stub(text)


def score_sentiment_stub(text: str) -> tuple[float, SentimentLabel]:
    lowered = text.lower()
    if any(token in lowered for token in ("broken", "blocked", "angry", "bad")):
        return -0.5, "negative"
    if any(token in lowered for token in ("great", "thanks", "love", "good")):
        return 0.5, "positive"
    return 0.0, "neutral"


def is_user_message(role: str) -> bool:
    return role == "user"
