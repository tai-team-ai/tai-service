"""Define the main entry point for the tai service API."""
from http.client import HTTPException
import traceback
from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
import torch
from .backend.backend import Backend
from .runtime_settings import SearchServiceSettings, BACKEND_ATTRIBUTE_NAME
from .routers import (
    class_resources,
    frequently_accessed_resources,
    search,
)

TITLE = "T.A.I. Service!"
DESCRIPTION = "A service for the T.A.I. project."

ROUTER = APIRouter()
ROUTER.get("/health-check")(lambda: {"status": "ok"})
ROUTER.get("/")(lambda: {"message": "Welcome to the T.A.I. Service API!"})
ROUTER.get("/cuda", include_in_schema=False)(lambda: {"cuda available": torch.cuda.is_available()})
ROUTERS = [
    ROUTER,
    class_resources.ROUTER,
    frequently_accessed_resources.ROUTER,
    search.ROUTER,
]

def create_app() -> FastAPI:
    """Create the FastAPI app."""
    runtime_settings = SearchServiceSettings()
    app = FastAPI(
        title=TITLE,
        description=DESCRIPTION,
    )
    backend = Backend(runtime_settings=runtime_settings)
    setattr(app.state, BACKEND_ATTRIBUTE_NAME, backend)
    # add exception handlers
    # configure CORS
    # TODO make this environment specific for dev and prod (also use the same values in the stack config for the api)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # add a logger to the middleware to log all requests
    @app.middleware("http")
    async def middleware(request: Request, call_next):
        response = await call_next(request)

        # Check and remove 'access-control-allow-origin' if exists to avoid conflict with AWS adding it's own
        if "access-control-allow-origin" in response.headers:
            del response.headers["access-control-allow-origin"]

        return response

    async def error_handler(_, exc):
        logger.error(f"Error occurred: {exc}")
        logger.critical(traceback.format_exc())
        return JSONResponse(status_code=500, content={"message": "Internal Server Error"})

    app.exception_handler(HTTPException)(error_handler)

    for router in ROUTERS:
        app.include_router(router)
    return app
