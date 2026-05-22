from fastapi import Header


async def verify_api_key(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> str:
    return x_api_key or ""
