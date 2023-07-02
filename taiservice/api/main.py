"""Define the main entry point for the tai service API."""
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
# first imports are for local development, second imports are for deployment
try:
    from .runtime_settings import TaiApiSettings, SETTINGS_STATE_ATTRIBUTE_NAME
    from .routers import (
        class_resources,
        tai
    )
except ImportError:
    from runtime_settings import TaiApiSettings, SETTINGS_STATE_ATTRIBUTE_NAME
    from routers import (
        class_resources,
        tai
    )

TITLE = "T.A.I. Service"
DESCRIPTION = "A service for the T.A.I. project."

ROUTER = APIRouter()
ROUTER.get("/health-check")(lambda: {"status": "ok"})
ROUTERS = [
    class_resources.ROUTER,
    tai.ROUTER,
    ROUTER,
]

def create_app() -> FastAPI:
    """Create the FastAPI app."""
    runtime_settings = TaiApiSettings()
    app = FastAPI(
        title=TITLE,
        description=DESCRIPTION,
    )
    setattr(app.state, SETTINGS_STATE_ATTRIBUTE_NAME, runtime_settings)
    # add exception handlers
    # configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # add a logger to the middleware to log all requests
    @app.middleware("http")
    async def log_requests(request, call_next):
        """Log all requests."""
        logger.info(f"Request: {request}")
        response = await call_next(request)
        return response

    for router in ROUTERS:
        app.include_router(router)
    return app
