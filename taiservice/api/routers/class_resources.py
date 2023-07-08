"""Define CRUD endpoints for class resources."""
from fastapi import APIRouter, Request
# first imports are for local development, second imports are for deployment
try:
    from .class_resources_schema import ClassResource, ClassResources, ClassResourceIds
    from ..taibackend.backend import ClassResourcesBackend
    from ..runtime_settings import BACKEND_ATTRIBUTE_NAME
except ImportError:
    from routers.class_resources_schema import ClassResource, ClassResources, ClassResourceIds
    from taibackend.backend import ClassResourcesBackend
    from runtime_settings import BACKEND_ATTRIBUTE_NAME


ROUTER = APIRouter()


@ROUTER.get("/class_resources", response_model=ClassResources)
def get_class_resources(ids: ClassResourceIds, request: Request):
    """Get all class resources."""
    backend: ClassResourcesBackend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    class_resource_docs = backend.get_class_resources(ids)
    return ClassResources(class_resources=class_resource_docs)


@ROUTER.post("/class_resources")
def create_class_resource(class_resource: ClassResource, request: Request):
    """Create a class resource."""
    backend: ClassResourcesBackend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    backend.create_class_resources([class_resource])
