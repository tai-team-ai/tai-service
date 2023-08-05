"""Define CRUD endpoints for class resources."""
from fastapi import APIRouter, Request, Response, status
from ...api.routers.class_resources_schema import ClassResources, ClassResourceIds
from ..backend.backend import Backend
from ...searchservice.backend.databases.errors import DuplicateClassResourceError
from ..runtime_settings import BACKEND_ATTRIBUTE_NAME


ROUTER = APIRouter()


@ROUTER.get("/class_resources", response_model=ClassResources)
def get_class_resources(ids: ClassResourceIds, request: Request, from_class_ids: bool = True):
    """Get all class resources."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    class_resource_docs = backend.get_class_resources(ids, from_class_ids=from_class_ids)
    return ClassResources(class_resources=class_resource_docs)


@ROUTER.post("/class_resources")
def create_class_resource(class_resources: ClassResources, request: Request, response: Response):
    """Create a class resource."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    try:
        backend.create_class_resources(class_resources)
    except DuplicateClassResourceError as error:
        response.status_code = status.HTTP_409_CONFLICT
        return {"message": error.message}
