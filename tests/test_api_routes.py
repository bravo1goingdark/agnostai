import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import get_session
from app.main import app


@pytest.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncClient:
    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_healthz_endpoint() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_insights_endpoint_requires_project_id(client: AsyncClient) -> None:
    response = await client.get("/v1/insights")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_insights_endpoint_returns_empty_for_unknown_project(
    client: AsyncClient,
) -> None:
    response = await client.get("/v1/insights?project_id=missing-project")
    assert response.status_code == 200
    data = response.json()
    assert data["total_messages"] == 0
    assert data["total_topics"] == 0


@pytest.mark.asyncio
async def test_topics_endpoint_requires_project_id(client: AsyncClient) -> None:
    response = await client.get("/v1/topics")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_topics_endpoint_returns_empty_for_unknown_project(
    client: AsyncClient,
) -> None:
    response = await client.get("/v1/topics?project_id=missing-project")
    assert response.status_code == 200
    data = response.json()
    assert data["topics"] == []


@pytest.mark.asyncio
async def test_reports_endpoint_requires_project_id(client: AsyncClient) -> None:
    response = await client.get("/v1/reports/current")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reports_endpoint_returns_empty_for_unknown_project(
    client: AsyncClient,
) -> None:
    response = await client.get(
        "/v1/reports/current?project_id=missing-project"
    )
    assert response.status_code == 200
    data = response.json()
    assert "No cluster run available" in data["report_text"]


@pytest.mark.asyncio
async def test_root_serves_dashboard() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_demo_bootstrap_rejects_empty_body(client: AsyncClient) -> None:
    response = await client.post("/v1/demo/bootstrap", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_topic_detail_404_for_unknown_id(client: AsyncClient) -> None:
    response = await client.get(
        "/v1/topics/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404
