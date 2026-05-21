def render_empty_report(project_id: str) -> str:
    return (
        "# Agnost Insights Report\n\n"
        f"Project: {project_id}\n\n"
        "No cluster run available.\n"
    )


def render_topic_report(
    project_id: str,
    topics: list[dict[str, object]],
    cluster_run_id: str | None = None,
) -> str:
    lines = ["# Agnost Insights Report", "", f"Project: {project_id}", ""]
    if cluster_run_id is not None:
        lines.extend([f"Latest cluster run: {cluster_run_id}", ""])
    if not topics:
        lines.append(
            "No cluster run available."
            if cluster_run_id is None
            else "No topics found in latest cluster run."
        )
        return "\n".join(lines).strip() + "\n"

    lines.append("Top topics:")
    for topic in topics:
        label = str(topic.get("label", "topic"))
        member_count = topic.get("member_count", 0)
        summary = topic.get("summary")
        lines.append(f"- {label} ({member_count} messages)")
        if summary:
            lines.append(f"  - {summary}")
    return "\n".join(lines).strip() + "\n"
