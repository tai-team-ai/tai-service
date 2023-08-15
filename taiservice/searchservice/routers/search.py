"""Define the TAI Search API endpoint."""
from fastapi import APIRouter, Request
from taiservice.api.routers.tai_schemas import (
    SearchResults,
    SearchQuery,
    ResourceSearchQuery,
)
from ..backend.backend import Backend
from ..runtime_settings import BACKEND_ATTRIBUTE_NAME

ROUTER = APIRouter()


@ROUTER.post("/search_engine", response_model=SearchResults)
def search(search_query: SearchQuery, request: Request):
    """Define the search endpoint."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    return backend.search(search_query, for_tai_tutor=False)

@ROUTER.post("/tutor_search", response_model=SearchResults)
def tutor_search(search_query: ResourceSearchQuery, request: Request):
    """Define the search endpoint."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    return backend.search(search_query, for_tai_tutor=True)
