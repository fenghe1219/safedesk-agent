import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import auth, cases, demo, health, knowledge, me, messages, tickets
from app.core.config import settings
from app.core.errors import register_exception_handlers
from app.core.security import new_id
from app.db.session import engine
from app.seed import seed_demo_data

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.seed_demo:
        try:
            await seed_demo_data()
        except Exception:
            logger.exception("Demo seed failed; API will still start")
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="SafeDesk API",
        version=settings.api_version,
        description="可审计、可评估、可人工接管的企业服务台 Agent API",
        docs_url=f"{settings.api_prefix}/docs",
        redoc_url=None,
        openapi_url=f"{settings.api_prefix}/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or new_id("req")
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

    register_exception_handlers(app)
    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(auth.router, prefix=settings.api_prefix)
    app.include_router(me.router, prefix=settings.api_prefix)
    app.include_router(demo.router, prefix=settings.api_prefix)
    app.include_router(cases.router, prefix=settings.api_prefix)
    app.include_router(messages.router, prefix=settings.api_prefix)
    app.include_router(knowledge.router, prefix=settings.api_prefix)
    app.include_router(tickets.router, prefix=settings.api_prefix)
    app.include_router(tickets.case_router, prefix=settings.api_prefix)

    @app.get(settings.api_prefix, include_in_schema=False)
    async def api_root() -> JSONResponse:
        return JSONResponse(
            {
                "name": settings.app_name,
                "version": settings.api_version,
                "docs": f"{settings.api_prefix}/docs",
            }
        )

    return app


app = create_app()
