from fastapi import APIRouter

from app.api.routes import admin, auth, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/api/v1")
api_router.include_router(admin.router, prefix="/api/v1")
