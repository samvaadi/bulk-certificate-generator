from fastapi import APIRouter
from app.api.jobs import router as jobs_router
from app.api.certificates import router as certificates_router

router = APIRouter(prefix="/api/v1")
router.include_router(jobs_router)
router.include_router(certificates_router)
