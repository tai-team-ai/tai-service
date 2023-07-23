"""Define endpoints that get common resources and questions from the database."""
from fastapi import APIRouter, Request
# first imports are for local development, second imports are for deployment
try:
    from ..runtime_settings import BACKEND_ATTRIBUTE_NAME
    from ..taibackend.backend import Backend
    from .common_resources_schema import CommonResources, CommonQuestions
except ImportError:
    from runtime_settings import BACKEND_ATTRIBUTE_NAME
    from taibackend.backend import Backend
    from routers.common_resources_schema import CommonResources, CommonQuestions


ROUTER = APIRouter()


@ROUTER.get("/common_resources", response_model=CommonResources)
def get_common_resources(request: Request):
    """Get all common resources."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    return CommonResources.Config.schema_extra["example"]


@ROUTER.get("/common_questions", response_model=CommonQuestions)
def get_common_questions(request: Request):
    """Get all common questions."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    return CommonQuestions.Config.schema_extra["example"]
