"""Define the TAI Search API endpoint."""
from fastapi import APIRouter, Request
from taiservice.api.routers.tai_schemas import (
    SearchQuery,
    ResourceSearchQuery,
)
from taiservice.api.taibackend.shared_schemas import SearchEngineResponse
from ..backend.backend import Backend
from ..runtime_settings import BACKEND_ATTRIBUTE_NAME

ROUTER = APIRouter()


@ROUTER.post("/search-engine", response_model=SearchEngineResponse)
def search(search_query: ResourceSearchQuery, request: Request):
    """Define the search endpoint."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    return backend.search(search_query, for_tai_tutor=False)

@ROUTER.post("/tutor-search", response_model=SearchEngineResponse)
def tutor_search(search_query: SearchQuery, request: Request):
    """Define the search endpoint."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    return backend.search(search_query, for_tai_tutor=True)
