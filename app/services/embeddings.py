from app.config import get_settings


def embedding_metadata() -> dict[str, object]:
    settings = get_settings()
    return {
        "model_name": settings.embedding_model_name,
        "dimension": settings.embedding_dimension,
    }

