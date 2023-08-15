"""Define the TAI Search API endpoint."""
from fastapi import APIRouter, Request
from taiservice.api.routers.tai_schemas import (
    SearchAnswer,
    ResourceSearchQuery,
)
from ..backend.backend import Backend
from ..runtime_settings import BACKEND_ATTRIBUTE_NAME

ROUTER = APIRouter()


@ROUTER.post("/search", response_model=SearchAnswer)
def search(search_query: ResourceSearchQuery, request: Request):
    """Define the search endpoint."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    return backend.search(search_query)