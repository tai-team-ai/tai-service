"""Define CRUD endpoints for class resources."""
from fastapi import APIRouter, Request, Response, status, BackgroundTasks
from ...api.routers.class_resources_schema import ClassResource, ClassResources, ClassResourceIds
from ..backend.backend import Backend, ServerOverloadedError
from ...searchservice.backend.databases.errors import DuplicateClassResourceError
from ..runtime_settings import BACKEND_ATTRIBUTE_NAME


ROUTER = APIRouter()


@ROUTER.get("/class-resources", response_model=ClassResources)
def get_class_resources(ids: ClassResourceIds, request: Request, from_class_ids: bool = True):
    """Get all class resources."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    class_resource_docs = backend.get_class_resources(ids, from_class_ids=from_class_ids)
    return ClassResources(class_resources=class_resource_docs)


@ROUTER.post("/class-resources")
def create_class_resource(
    class_resource: ClassResource,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
):
    """Create a class resource."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    try:
        background_callable = backend.create_class_resource(class_resource)
        background_tasks.add_task(background_callable)
        response.status_code = status.HTTP_202_ACCEPTED
        return {"message": "Class resource creation processing."}
    except (DuplicateClassResourceError, ServerOverloadedError) as error:
        if isinstance(error, DuplicateClassResourceError):
            response.status_code = status.HTTP_409_CONFLICT
        elif isinstance(error, ServerOverloadedError):
            response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
        else:
            response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"message": error.message}
