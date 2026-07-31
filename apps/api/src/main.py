import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Literal
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry import trace
from pydantic import BaseModel
from sqlalchemy import text

from src.jobs.worker import Worker
from src.lib.body_limit import BodySizeLimitMiddleware
from src.lib.config import settings
from src.lib.database import async_session_factory
from src.lib.logging import configure_logging, get_logger
from src.lib.storage import aclose_storage_provider
from src.lib.telemetry import configure_telemetry, instrument_app

# Configure logging first
configure_logging()
logger = get_logger(__name__)

# Ensure ORM models are registered on Base.metadata (SQLite test create_all).
import src.channels.models  # noqa: E402
import src.conflict.models  # noqa: E402
import src.eval.models  # noqa: E402
import src.glossary.models  # noqa: E402
import src.graph.models  # noqa: E402
import src.jobs.queue  # noqa: E402
import src.review.models  # noqa: E402
import src.tenancy.models  # noqa: E402, F401


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    logger.info("Starting application", env=settings.PROJECT_ENV)
    configure_telemetry()
    instrument_app(app)

    worker_task: asyncio.Task[None] | None = None
    worker: Worker | None = None
    db_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
    if (
        settings.MISTRAL_API_KEY
        and not settings.MISTRAL_KILL_SWITCH
        and not db_is_sqlite
    ):
        from src.jobs.kinds.ingest_document import handle_ingest_document
        from src.jobs.kinds.regenerate_rendition import handle_regenerate_rendition
        from src.jobs.kinds.send_package import handle_send_package
        from src.jobs.queue import JobKind

        worker = Worker(
            session_factory=async_session_factory,
            handlers={
                JobKind.ingest_document.value: handle_ingest_document,
                JobKind.send_package.value: handle_send_package,
                JobKind.regenerate_rendition.value: handle_regenerate_rendition,
            },
        )
        worker_task = asyncio.create_task(worker.run_forever(), name="job-worker")
        logger.info("Job worker started", worker_id=worker.worker_id)
    else:
        logger.warning(
            "Job worker not started — need MISTRAL_API_KEY, kill-switch off, "
            "and a non-SQLite database"
        )

    yield

    # Shutdown
    if worker is not None:
        worker.stop()
    if worker_task is not None:
        worker_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker_task
    logger.info("Shutting down application")
    await aclose_storage_provider()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.PROJECT_ENV != "prod" else None,
    redoc_url="/redoc" if settings.PROJECT_ENV != "prod" else None,
)


# Request ID middleware
@app.middleware("http")
async def request_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Add request ID to each request for tracing."""
    request_id = request.headers.get("X-Request-ID", str(uuid4()))

    # Bind request ID to structlog context
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    # Add to current span
    span = trace.get_current_span()
    if span.is_recording():
        span.set_attribute("request.id", request_id)

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Error response model
class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str
    message: str
    request_id: str | None = None
    trace_id: str | None = None


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle all unhandled exceptions with consistent format."""
    request_id = request.headers.get("X-Request-ID")

    # Get trace context
    span = trace.get_current_span()
    trace_id = None
    if span.is_recording():
        ctx = span.get_span_context()
        trace_id = format(ctx.trace_id, "032x")
        span.record_exception(exc)
        span.set_status(trace.StatusCode.ERROR, str(exc))

    # Log the exception
    logger.exception(
        "Unhandled exception",
        exc_info=exc,
        request_id=request_id,
        path=request.url.path,
        method=request.method,
    )

    # Return consistent error response
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="internal_server_error",
            message="An unexpected error occurred"
            if settings.PROJECT_ENV == "prod"
            else str(exc),
            request_id=request_id,
            trace_id=trace_id,
        ).model_dump(),
    )


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Body size limit (edge WAFs inspect only the first 8 KB and cannot
# enforce payload size, so the real limit lives here)
app.add_middleware(BodySizeLimitMiddleware, max_body_size=settings.MAX_BODY_SIZE)


class ServiceStatus(BaseModel):
    """Individual service health status."""

    status: Literal["healthy", "unhealthy"]
    latency_ms: float | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    """Health check response with detailed service statuses."""

    status: Literal["healthy", "degraded", "unhealthy"]
    version: str = "0.1.0"
    services: dict[str, ServiceStatus]


async def check_database() -> ServiceStatus:
    """Check database connectivity."""
    import time

    start = time.perf_counter()
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        latency = (time.perf_counter() - start) * 1000
        return ServiceStatus(status="healthy", latency_ms=round(latency, 2))
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ServiceStatus(
            status="unhealthy", latency_ms=round(latency, 2), error=str(e)
        )


async def check_redis() -> ServiceStatus | None:
    """Check Redis connectivity if configured."""
    import time

    if not settings.REDIS_URL:
        return None

    start = time.perf_counter()
    try:
        import redis.asyncio as redis

        client = redis.from_url(settings.REDIS_URL)
        await client.ping()
        await client.aclose()
        latency = (time.perf_counter() - start) * 1000
        return ServiceStatus(status="healthy", latency_ms=round(latency, 2))
    except ImportError:
        return ServiceStatus(status="unhealthy", error="redis package not installed")
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ServiceStatus(
            status="unhealthy", latency_ms=round(latency, 2), error=str(e)
        )


@app.get("/health")
async def health_check() -> HealthResponse:
    """Detailed health check endpoint with service statuses."""
    services: dict[str, ServiceStatus] = {}

    # Check database
    services["database"] = await check_database()

    # Check Redis (if configured)
    redis_status = await check_redis()
    if redis_status:
        services["redis"] = redis_status

    # Determine overall status
    statuses = [s.status for s in services.values()]
    if all(s == "healthy" for s in statuses):
        overall_status: Literal["healthy", "degraded", "unhealthy"] = "healthy"
    elif all(s == "unhealthy" for s in statuses):
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        version="0.1.0",
        services=services,
    )


@app.get("/health/live")
async def liveness_check() -> dict[str, str]:
    """Simple liveness probe for Kubernetes."""
    return {"status": "ok"}


@app.get("/health/ready")
async def readiness_check() -> dict[str, str]:
    """Readiness probe - checks if app can serve traffic."""
    db_status = await check_database()
    if db_status.status == "unhealthy":
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not ready",
        )
    return {"status": "ready"}


# Register routers here
from src.auth.router import router as auth_router  # noqa: E402
from src.channels.router import router as channels_router  # noqa: E402
from src.conflict.router import router as conflict_router  # noqa: E402
from src.documents.router import router as documents_router  # noqa: E402
from src.eval.router import router as eval_router  # noqa: E402
from src.glossary.router import router as glossary_router  # noqa: E402
from src.graph.router import router as graph_router  # noqa: E402
from src.notifications.router import router as notifications_router  # noqa: E402
from src.orgs.router import router as orgs_router  # noqa: E402
from src.profiles.router import router as profiles_router  # noqa: E402
from src.review.router import router as review_router  # noqa: E402
from src.teams.router import router as teams_router  # noqa: E402

app.include_router(auth_router, prefix="/api/auth", tags=["authentication"])
app.include_router(orgs_router, prefix="/api/orgs", tags=["orgs"])
app.include_router(teams_router, prefix="/api", tags=["teams"])
app.include_router(profiles_router, prefix="/api", tags=["profiles"])
app.include_router(documents_router, prefix="/api", tags=["documents"])
app.include_router(glossary_router, prefix="/api", tags=["glossary"])
app.include_router(notifications_router, prefix="/api", tags=["notifications"])
app.include_router(graph_router, prefix="/api", tags=["graph"])
app.include_router(conflict_router, prefix="/api", tags=["conflict"])
app.include_router(channels_router, prefix="/api", tags=["channels"])
app.include_router(review_router, prefix="/api", tags=["review"])
app.include_router(eval_router, prefix="/api", tags=["eval"])

