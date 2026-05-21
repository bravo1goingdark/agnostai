def render_empty_report(project_id: str) -> str:
    return (
        "# Agnost Insights Report\n\n"
        f"Project: {project_id}\n\n"
        "No cluster run available.\n"
    )
