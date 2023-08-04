"""Define CRUD endpoints for class resources."""
from fastapi import APIRouter, Request, Response
# first imports are for local development, second imports are for deployment
try:
    from .class_resources_schema import ClassResource, ClassResources, ClassResourceIds
    from ..taibackend.backend import Backend
    from ..runtime_settings import BACKEND_ATTRIBUTE_NAME
except ImportError as e:
    from routers.class_resources_schema import ClassResources, ClassResourceIds
    from taibackend.backend import Backend
    from runtime_settings import BACKEND_ATTRIBUTE_NAME


ROUTER = APIRouter()


@ROUTER.get("/class_resources", response_model=ClassResources)
def get_class_resources(ids: ClassResourceIds, request: Request, from_class_ids: bool = True):
    """Get all class resources."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    class_resource_docs = backend.get_class_resources(ids, from_class_ids=from_class_ids)
    return ClassResources(class_resources=class_resource_docs)


@ROUTER.post("/class_resources")
def create_class_resource(class_resource: ClassResource, request: Request, response: Response):
    """Create a class resource."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    # try:
    class_resources = ClassResources(class_resources=[class_resource])
    backend.create_class_resources(class_resources)
    # except DuplicateClassResourceError as error:
    #     response.status_code = status.HTTP_409_CONFLICT
    #     return {"message": error.message}
