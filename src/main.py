import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from src.core.config import settings
from src.core.logging import setup_logging

setup_logging(settings.log_level)

logger = logging.getLogger("upload-job-service")

app = FastAPI(title="Upload Job Service", version="1.0.0")

Instrumentator().instrument(app).expose(app)


@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
    import logging as _logging

    old_factory = _logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.trace_id = trace_id
        return record

    _logging.setLogRecordFactory(record_factory)
    try:
        response = await call_next(request)
    finally:
        _logging.setLogRecordFactory(old_factory)
    response.headers["X-Trace-ID"] = trace_id
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Erro interno do servidor"})


# Routers
from src.api.health import router as health_router  # noqa: E402
from src.api.jobs_router import router as jobs_router  # noqa: E402

app.include_router(health_router)
app.include_router(jobs_router)


@app.get("/ping")
async def ping() -> dict:
    return {"pong": True}
