"""Define endpoints that get common resources and questions from the database."""
from fastapi import APIRouter, Request, Response
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


@ROUTER.get("/frequently-accessed-resources/{class_id}", response_model=FrequentlyAccessedResources)
def get_frequently_accessed_resources(request: Request, response: Response, class_id: str):
    """
    Get frequently accessed resources for a specific class."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    try:
        resources = backend.get_frequently_accessed_class_resources(class_id)
    except Exception: # pylint: disable=broad-except
        response.status_code = 500
        return FrequentlyAccessedResources(resources=[])
    return resources


@ROUTER.get("/common-questions/{class_id}", response_model=CommonQuestions)
def get_common_questions(request: Request, response: Response, class_id: str):
    """Get all common questions."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    try:
        questions = backend.get_frequently_asked_questions(class_id)
    except Exception: # pylint: disable=broad-except
        response.status_code = 500
        return CommonQuestions(questions=[])
    return questions
