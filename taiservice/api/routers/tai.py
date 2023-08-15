"""Define the API endpoints for the AI responses."""
from fastapi import APIRouter, Request
try:
    from .tai_schemas import(
        SearchResults,
        ResourceSearchQuery,
        ChatSessionRequest,
        ChatSessionResponse,
    )
    from ..taibackend.backend import Backend
    from ..runtime_settings import BACKEND_ATTRIBUTE_NAME
except ImportError:
    from routers.tai_schemas import (
        SearchResults,
        ResourceSearchQuery,
        ChatSessionRequest,
        ChatSessionResponse,
    )
    from taibackend.backend import Backend
    from runtime_settings import BACKEND_ATTRIBUTE_NAME


ROUTER = APIRouter()


@ROUTER.post("/chat", response_model=ChatSessionResponse)
def chat(chat_session: ChatSessionRequest, request: Request):
    """Define the chat endpoint."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    chat_session = backend.get_tai_response(chat_session)
    return ChatSessionResponse.parse_obj(chat_session)


@ROUTER.post("/search", response_model=SearchResults)
def search(search_query: ResourceSearchQuery, request: Request):
    """Define the search endpoint."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    return backend.search(search_query, result_type="results")


@ROUTER.post("/search-summary")
def search_summary(search_query: ResourceSearchQuery, request: Request) -> str:
    """Define the search endpoint."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    return backend.search(search_query, result_type="summary")
