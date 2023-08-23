"""Define CRUD endpoints for class resources."""
import traceback
from fastapi import APIRouter, Request, Response, status
from loguru import logger
# first imports are for local development, second imports are for deployment
try:
    from .class_resources_schema import ClassResources, ClassResourceIds, FailedResources
    from ..taibackend.backend import Backend
    from ..runtime_settings import BACKEND_ATTRIBUTE_NAME
except ImportError as e:
    from routers.class_resources_schema import ClassResources, ClassResourceIds
    from taibackend.backend import Backend
    from runtime_settings import BACKEND_ATTRIBUTE_NAME


ROUTER = APIRouter()


@ROUTER.get("/class-resources", response_model=ClassResources)
def get_class_resources(ids: ClassResourceIds, request: Request, response: Response, from_class_ids: bool = True):
    """Get all class resources."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    try:
        class_resource_docs = backend.get_class_resources(ids, from_class_ids=from_class_ids)
    except Exception: # pylint: disable=broad-except
        logger.error(traceback.format_exc())
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return ClassResources(class_resources=[])
    return ClassResources(class_resources=class_resource_docs)


@ROUTER.post("/class-resources", response_model=FailedResources)
def create_class_resource(class_resources: ClassResources, request: Request, response: Response):
    """Create a class resource."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    failed_resources = backend.create_class_resources(class_resources)
    if len(failed_resources.failed_resources) > 0:
        logger.info(f"Class resources: {class_resources.class_resources}")
        logger.warning(f"Failed resources: {failed_resources}")
    if len(failed_resources.failed_resources) < len(class_resources.class_resources) and len(failed_resources.failed_resources) > 0:
        response.status_code = status.HTTP_207_MULTI_STATUS
    elif len(failed_resources.failed_resources) == len(class_resources.class_resources):
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    else:
        response.status_code = status.HTTP_202_ACCEPTED
    return failed_resources
