"""Define the main entry point for the tai service API."""
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from .taibackend import class_resources

from taiservice.api.taibackend import class_resources
# first imports are for local development, second imports are for deployment
try:
    from .runtime_settings import TaiApiSettings, BACKEND_ATTRIBUTE_NAME
    from .taibackend.backend import Backend
    from .routers import (
        tai
    )
except ImportError as e:
    from runtime_settings import TaiApiSettings, BACKEND_ATTRIBUTE_NAME
    from taibackend.backend import Backend
    from routers import (
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
    backend = Backend(runtime_settings=runtime_settings)
    setattr(app.state, BACKEND_ATTRIBUTE_NAME, backend)
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
