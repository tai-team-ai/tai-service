"""Define the main entry point for the tai service API."""
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from runtime_settings import TaiApiSettings, SETTINGS_STATE_ATTRIBUTE_NAME


TITLE = "T.A.I. Service"
DESCRIPTION = "A service for the T.A.I. project."

ROUTER = APIRouter()

ROUTER.get("/health-check")(lambda: {"status": "ok"})
ROUTERS = [
    ROUTER
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

    for router in ROUTERS:
        app.include_router(router)
    return app
