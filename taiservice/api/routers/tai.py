"""Define the API endpoints for the AI responses."""
from fastapi import APIRouter, Request, Response, status
try:
    from ..taibackend.taitutors.errors import UserTokenLimitError
    from .tai_schemas import(
        SearchResults,
        ResourceSearchQuery,
        ChatSessionRequest,
        ChatSessionResponse,
    )
    from ..taibackend.backend import Backend
    from ..runtime_settings import BACKEND_ATTRIBUTE_NAME
except ImportError:
    from taibackend.taitutors.errors import UserTokenLimitError
    from routers.tai_schemas import (
        SearchResults,
        ResourceSearchQuery,
        ChatSessionRequest,
        ChatSessionResponse,
    )
    from taibackend.backend import Backend
    from runtime_settings import BACKEND_ATTRIBUTE_NAME


ROUTER = APIRouter()


def get_error_response(response: Response, exc: Exception) -> dict:
    """Handle exceptions."""
    if isinstance(exc, UserTokenLimitError):
        response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
        return {"message": "User token limit reached."}
    return {"message": "Internal server error."}


@ROUTER.post("/chat", response_model=ChatSessionResponse)
def chat(chat_session: ChatSessionRequest, request: Request, response: Response):
    """Define the chat endpoint."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    try:
        chat_session = backend.get_tai_response(chat_session)
        return ChatSessionResponse.parse_obj(chat_session)
    except Exception as e: # pylint: disable=broad-except
        return get_error_response(response, e)


@ROUTER.post("/search", response_model=SearchResults)
def search(search_query: ResourceSearchQuery, request: Request, response: Response):
    """Define the search endpoint."""
    try:
        backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
        return backend.search(search_query)
    except Exception as e: # pylint: disable=broad-except
        return get_error_response(response, e)


@ROUTER.post("/search-summary")
def search_summary(search_query: ResourceSearchQuery, request: Request, response: Response):
    """Define the search endpoint."""
    try:
        backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
        return backend.search(search_query, result_type="summary")
    except Exception as e: # pylint: disable=broad-except
        return get_error_response(response, e)
