from fastapi import APIRouter

from app.api.routes import (
    conversations,
    demo,
    health,
    insights,
    observability,
    reports,
    topics,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(conversations.router, prefix="/v1", tags=["conversations"])
api_router.include_router(demo.router, prefix="/v1", tags=["demo"])
api_router.include_router(insights.router, prefix="/v1", tags=["insights"])
api_router.include_router(observability.router, prefix="/v1", tags=["observability"])
api_router.include_router(reports.router, prefix="/v1", tags=["reports"])
api_router.include_router(topics.router, prefix="/v1", tags=["topics"])
