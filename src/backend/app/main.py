import asyncio
from contextlib import asynccontextmanager
from contextlib import suppress
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette import status

from agents.orchestrator import BitenaryChatOrchestrator
from api.routers import router as api_router
from bitenary_mcp.server import create_mcp_server
from bitenary_mcp.service.tokens import MCPTokenCodec
from core.config import Settings, get_settings
from core.csrf import CSRFMiddleware
from core.database import AsyncSessionLocal
from guest_chat.service import GuestChatRateLimiter
from ingredients.infrastructure.sqlalchemy_ingredients import SqlAlchemyIngredientRepository
from virtual_fridge.jobs.scan_expiry import run_scheduler as run_expiry_scheduler


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)
    mcp_server = create_mcp_server(settings)
    mcp_app = mcp_server.streamable_http_app()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # Seed ingredient master on first startup (idempotent).
        # Wrapped in try/except so the app still starts in test environments
        # where the DB table hasn't been created yet (no migration run).
        try:
            async with AsyncSessionLocal() as session:
                repo = SqlAlchemyIngredientRepository(session)
                seeded = await repo.seed_from_json()
                if seeded:
                    logging.getLogger(__name__).info(
                        "Ingredient seed complete: %d rows inserted.", seeded
                    )
        except Exception as exc:  # noqa: BLE001
            logging.getLogger(__name__).warning(
                "Ingredient seed skipped (table not ready?): %s", exc
            )

        orchestrator = BitenaryChatOrchestrator(
            settings,
            MCPTokenCodec(settings.mcp_token_pepper),
            AsyncSessionLocal,
        )
        _app.state.orchestrator = orchestrator
        guest_chat_rate_limiter = GuestChatRateLimiter(
            settings.redis_url,
            per_minute=settings.guest_chat_rate_limit_per_minute,
            per_day=settings.guest_chat_rate_limit_per_day,
        )
        _app.state.guest_chat_rate_limiter = guest_chat_rate_limiter
        await orchestrator.startup()
        await guest_chat_rate_limiter.startup()
        expiry_scan_task = None
        if settings.fridge_expiry_scan_enabled:
            expiry_scan_task = asyncio.create_task(
                run_expiry_scheduler(settings.fridge_expiry_scan_interval_seconds),
                name="fridge-expiry-notification-scanner",
            )
        try:
            async with mcp_server.session_manager.run():
                yield
        finally:
            if expiry_scan_task is not None:
                expiry_scan_task.cancel()
                with suppress(asyncio.CancelledError):
                    await expiry_scan_task
            await guest_chat_rate_limiter.shutdown()
            await orchestrator.shutdown()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug,
        lifespan=lifespan,
    )

    # Add CSRF first so CORS remains the outer middleware and decorates CSRF
    # rejection responses for the configured browser origins.
    app.add_middleware(
        CSRFMiddleware,
        secret=settings.csrf_secret,
        protected_prefix="/api",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logging.getLogger(__name__).exception(
            "Unhandled request error: %s %s",
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    app.include_router(api_router)
    # The fallback mount preserves the public endpoint as exactly /mcp while
    # allowing FastAPI REST routes to take precedence.
    app.mount("/", mcp_app, name="mcp")
    return app


app = create_app()
