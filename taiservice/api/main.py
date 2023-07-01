"""Define the main entry point for the tai service API."""
import importlib
from pathlib import Path
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
ROUTERS_DIR_NAME = "routers"
# first imports are for local development, second imports are for deployment
try:
    from taiservice.api.runtime_settings import TaiApiSettings, SETTINGS_STATE_ATTRIBUTE_NAME
    PACKAGE_PREFIX = f"taiservice.api.{ROUTERS_DIR_NAME}"
except ImportError:
    from runtime_settings import TaiApiSettings, SETTINGS_STATE_ATTRIBUTE_NAME
    PACKAGE_PREFIX = ROUTERS_DIR_NAME

TITLE = "T.A.I. Service"
DESCRIPTION = "A service for the T.A.I. project."

ROUTER = APIRouter()
ROUTER.get("/health-check")(lambda: {"status": "ok"})
ROUTERS_DIR = Path(__file__).parent / ROUTERS_DIR_NAME

def get_routers(router_dir: Path, package_prefix: str) -> list:
    """Add routers to the main router."""
    routers = []
    for file_path in router_dir.glob("*.py"):
        module_name = file_path.stem
        module = importlib.import_module(f"{package_prefix}.{module_name}")
        for attr_name in dir(module):
            attribute = getattr(module, attr_name)
            if isinstance(attribute, APIRouter):
                routers.append(attribute)
    return routers

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

    routers = get_routers(ROUTERS_DIR, PACKAGE_PREFIX)
    routers.append(ROUTER)
    for router in routers:
        app.include_router(router)
    return app
