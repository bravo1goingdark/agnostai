from typing import TypedDict

from app.config import get_settings


class EmbeddingMetadata(TypedDict):
    model_name: str
    dimension: int


def embedding_metadata() -> EmbeddingMetadata:
    settings = get_settings()
    return {
        "model_name": settings.embedding_model_name,
        "dimension": settings.embedding_dimension,
    }


def embed_text_stub(text: str, dimension: int) -> list[float]:
    seed = sum(ord(char) for char in text) or 1
    return [((seed + index) % 997) / 997.0 for index in range(dimension)]
