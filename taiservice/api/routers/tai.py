"""Define the API endpoints for the AI responses."""
from fastapi import APIRouter, Request, status, HTTPException
from loguru import logger
try:
    from ..taibackend.taitutors.errors import UserTokenLimitError, OverContextWindowError
    from ..taibackend.backend import Backend
    from .tai_schemas import(
        SearchResults,
        ResourceSearchQuery,
        ChatSessionRequest,
        ChatSessionResponse,
    )
    from ..runtime_settings import BACKEND_ATTRIBUTE_NAME
except ImportError:
    from taibackend.taitutors.errors import UserTokenLimitError, OverContextWindowError
    from taibackend.backend import Backend
    from routers.tai_schemas import (
        SearchResults,
        ResourceSearchQuery,
        ChatSessionRequest,
        ChatSessionResponse,
    )
    from runtime_settings import BACKEND_ATTRIBUTE_NAME


ROUTER = APIRouter()


def handle_error(exc: Exception) -> dict:
    """Handle exceptions."""
    if isinstance(exc, UserTokenLimitError):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=exc.message)
    elif isinstance(exc, OverContextWindowError):
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=exc.message)
    logger.error(exc)
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal Server Error")


@ROUTER.post("/chat", response_model=ChatSessionResponse)
def chat(chat_session: ChatSessionRequest, request: Request):
    """Define the chat endpoint."""
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    try:
        chat_session = backend.get_tai_response(chat_session)
        return ChatSessionResponse.parse_obj(chat_session)
    except Exception as e: # pylint: disable=broad-except
        handle_error(e)


@ROUTER.post("/search", response_model=SearchResults)
def search(search_query: ResourceSearchQuery, request: Request):
    """Define the search endpoint."""
    try:
        backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
        return backend.search(search_query, result_type="results")
    except Exception as e: # pylint: disable=broad-except
        return handle_error(e)


@ROUTER.post("/search-summary")
def search_summary(search_query: ResourceSearchQuery, request: Request):
    """Define the search endpoint."""
    try:
        backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
        return backend.search(search_query, result_type="summary")
    except Exception as e: # pylint: disable=broad-except
        return handle_error(e)
