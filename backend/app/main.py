import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from app.core.config import Settings, get_settings
from app.modules.documents.router import router as documents_router
from app.modules.documents.search_router import router as evidence_router
from app.modules.exports.router import router as exports_router
from app.modules.gaps.router import router as gaps_router
from app.modules.identity.router import router
from app.modules.matrix.router import router as matrix_router
from app.modules.projects.router import router as projects_router
from app.modules.references.router import router as references_router
from app.modules.writing.router import router as writing_router

logger = logging.getLogger("researchpilot")


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(
            config.database_url.get_secret_value(), pool_pre_ping=True, hide_parameters=True
        )
        app.state.session_factory = sessionmaker(engine, expire_on_commit=False)
        app.state.redis = Redis.from_url(
            config.redis_url.get_secret_value(), socket_timeout=2, socket_connect_timeout=2
        )
        app.state.engine = engine
        try:
            yield
        finally:
            app.state.redis.close()
            engine.dispose()

    app = FastAPI(title="ResearchPilot API", version="0.1.0", lifespan=lifespan)
    app.state.settings = config

    def problem(
        request: Request, status: int, detail: str, headers: Mapping[str, str] | None = None
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status,
            media_type="application/problem+json",
            headers=headers,
            content={
                "type": "about:blank",
                "title": "Request failed",
                "status": status,
                "detail": detail,
                "instance": request.url.path,
                "request_id": getattr(request.state, "request_id", "unknown"),
            },
        )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        return problem(request, error.status_code, str(error.detail), error.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        # Do not serialize Pydantic's input field: it may contain a raw password.
        return problem(request, 422, "Check the submitted fields and try again")

    @app.exception_handler(OSError)
    @app.exception_handler(SQLAlchemyError)
    @app.exception_handler(RedisError)
    async def infrastructure_error(request: Request, error: Exception) -> JSONResponse:
        logger.warning(
            "dependency_unavailable request_id=%s category=%s",
            request.state.request_id,
            type(error).__name__,
        )
        return problem(request, 503, "Service temporarily unavailable")

    @app.get("/api/v1/health/live", tags=["operations"])
    def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/api/v1/health/ready", tags=["operations"])
    async def ready() -> dict[str, str]:
        def probe() -> None:
            with app.state.engine.connect() as connection:
                assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0014"
                connection.execute(text("SELECT id, token_hash, csrf_hash FROM sessions LIMIT 0"))
                connection.execute(
                    text("SELECT id, owner_id, revision FROM research_projects LIMIT 0")
                )
                connection.execute(text("SELECT id, project_id, sha256 FROM documents LIMIT 0"))
                connection.execute(
                    text("SELECT document_id, state, lease_token FROM document_jobs LIMIT 0")
                )
            app.state.redis.ping()

        try:
            await run_in_threadpool(probe)
        except Exception:
            raise HTTPException(503, "Dependencies or migrations are not ready") from None
        return {"status": "ready"}

    app.include_router(router)
    app.include_router(projects_router)
    app.include_router(documents_router)
    app.include_router(evidence_router)
    app.include_router(matrix_router)
    app.include_router(gaps_router)
    app.include_router(references_router)
    app.include_router(writing_router)
    app.include_router(exports_router)
    return app
