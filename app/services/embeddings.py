from typing import TypedDict

from app.config import get_settings


class EmbeddingMetadata(TypedDict):
    model_name: str
    dimension: int


_embedding_model: object | None = None


def _get_embedding_model() -> object | None:
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer

            _embedding_model = SentenceTransformer(
                get_settings().embedding_model_name
            )
        except Exception:
            _embedding_model = False
    return _embedding_model if _embedding_model is not False else None


def embedding_metadata() -> EmbeddingMetadata:
    settings = get_settings()
    return {
        "model_name": settings.embedding_model_name,
        "dimension": settings.embedding_dimension,
    }


def embed_text(text: str, dimension: int) -> list[float]:
    model = _get_embedding_model()
    if model is not None:
        return model.encode([text])[0].tolist()  # type: ignore[attr-defined, no-any-return]
    return embed_text_stub(text, dimension)


def embed_text_stub(text: str, dimension: int) -> list[float]:
    seed = sum(ord(char) for char in text) or 1
    return [((seed + index) % 997) / 997.0 for index in range(dimension)]
