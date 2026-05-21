from fastapi import APIRouter

from app.api.routes import conversations, health, insights, topics

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(conversations.router, prefix="/v1", tags=["conversations"])
api_router.include_router(insights.router, prefix="/v1", tags=["insights"])
api_router.include_router(topics.router, prefix="/v1", tags=["topics"])

