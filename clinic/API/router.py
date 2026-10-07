from fastapi import APIRouter

from API.routes import (
    admin,
    appointments,
    auth,
    encounters,
    health,
    medical_histories,
    patients,
    reception,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/api/v1")
api_router.include_router(admin.router, prefix="/api/v1")
api_router.include_router(patients.router, prefix="/api/v1")
api_router.include_router(medical_histories.router, prefix="/api/v1")
api_router.include_router(appointments.router, prefix="/api/v1")
api_router.include_router(reception.router, prefix="/api/v1")
api_router.include_router(encounters.router, prefix="/api/v1")
