from fastapi import APIRouter

from app.api.account import router as account_router
from app.api.auth import router as auth_router
from app.api.grades import router as grades_router
from app.api.schedule import router as schedule_router
from app.api.settings import router as settings_router


api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(account_router)
api_router.include_router(schedule_router)
api_router.include_router(grades_router)
api_router.include_router(settings_router)
