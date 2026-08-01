from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette import status

from agents.orchestrator import BitenaryChatOrchestrator
from api.routers import router as api_router
from bitenary_mcp.server import create_mcp_server
from core.config import Settings, get_settings
from core.database import AsyncSessionLocal
from ingredients.infrastructure.sqlalchemy_ingredients import SqlAlchemyIngredientRepository


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

        orchestrator = BitenaryChatOrchestrator(settings)
        _app.state.orchestrator = orchestrator
        await orchestrator.startup()
        async with mcp_server.session_manager.run():
            yield
        await orchestrator.shutdown()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug,
        lifespan=lifespan,
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
