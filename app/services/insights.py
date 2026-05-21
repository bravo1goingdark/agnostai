def empty_insights(project_id: str) -> dict[str, object]:
    return {
        "project_id": project_id,
        "topics": [],
        "sentiment_distribution": {},
        "emerging_topics": [],
    }

