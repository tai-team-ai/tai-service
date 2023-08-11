"""Define endpoints that get common resources and questions from the database."""
from fastapi import APIRouter, Request
from ..runtime_settings import BACKEND_ATTRIBUTE_NAME
from ..backend.backend import Backend
from ...api.routers.common_resources_schema import FrequentlyAccessedResources


ROUTER = APIRouter()


@ROUTER.get("/frequently_accessed_resources/{class_id}", response_model=FrequentlyAccessedResources)
def get_frequently_accessed_resources(request: Request, class_id: str):
    """
    Get frequently accessed resources for a specific class."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    return backend.get_frequently_accessed_class_resources(class_id)
