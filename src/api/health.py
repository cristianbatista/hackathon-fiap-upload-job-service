from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "upload-job-service"})
