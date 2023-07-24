"""Define endpoints that get common resources and questions from the database."""
from fastapi import APIRouter, Request
# first imports are for local development, second imports are for deployment
try:
    from ..runtime_settings import BACKEND_ATTRIBUTE_NAME
    from ..taibackend.backend import Backend
    from .common_resources_schema import FrequentlyAccessedResources, CommonQuestions
except ImportError:
    from runtime_settings import BACKEND_ATTRIBUTE_NAME
    from taibackend.backend import Backend
    from routers.common_resources_schema import FrequentlyAccessedResources, CommonQuestions


ROUTER = APIRouter()


@ROUTER.get("/frequently_accessed_resources/{class_id}", response_model=FrequentlyAccessedResources)
def get_frequently_accessed_resources(request: Request, class_id: str):
    """
    Get frequently accessed resources for a specific class."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    return backend.get_frequently_accessed_class_resources(class_id)


@ROUTER.get("/common_questions", response_model=CommonQuestions)
def get_common_questions(request: Request):
    """Get all common questions."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    return CommonQuestions.Config.schema_extra["example"]
