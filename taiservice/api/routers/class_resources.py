"""Define CRUD endpoints for class resources."""
from fastapi import APIRouter, Request, Response, status
# first imports are for local development, second imports are for deployment
try:
    from .class_resources_schema import ClassResources, ClassResourceIds
    from ..taibackend.backend import Backend, DuplicateResourceError
    from ..runtime_settings import BACKEND_ATTRIBUTE_NAME
except ImportError as e:
    from routers.class_resources_schema import ClassResources, ClassResourceIds
    from taibackend.backend import Backend, DuplicateResourceError
    from runtime_settings import BACKEND_ATTRIBUTE_NAME


ROUTER = APIRouter()


@ROUTER.get("/class-resources", response_model=ClassResources)
def get_class_resources(ids: ClassResourceIds, request: Request, from_class_ids: bool = True):
    """Get all class resources."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    class_resource_docs = backend.get_class_resources(ids, from_class_ids=from_class_ids)
    return ClassResources(class_resources=class_resource_docs)


@ROUTER.post("/class-resources")
def create_class_resource(class_resources: ClassResources, request: Request, response: Response):
    """Create a class resource."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    try:
        backend.create_class_resources(class_resources)
    except DuplicateResourceError as error:
        response.status_code = status.HTTP_409_CONFLICT
        return {"message": error.message}
