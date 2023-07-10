"""Define the API endpoints for the AI responses."""
from uuid import uuid4
from fastapi import APIRouter, Request
try:
    from .tai_schemas import(
        ResourceSearchAnswer,
        ResourceSearchQuery,
        TaiSearchResponse,
        ClassResourceSnippet,
        ChatSessionRequest,
        ChatSessionResponse,
    )
    from ..routers.class_resources_schema import ClassResourceType, Metadata
    from ..taibackend.backend import Backend
    from ..runtime_settings import BACKEND_ATTRIBUTE_NAME
except ImportError:
    from routers.tai_schemas import (
        ResourceSearchAnswer,
        ResourceSearchQuery,
        TaiSearchResponse,
        ClassResourceSnippet,
        ChatSessionRequest,
        ChatSessionResponse,
    )
    from routers.class_resources_schema import ClassResourceType, Metadata
    from taibackend.backend import Backend
    from runtime_settings import BACKEND_ATTRIBUTE_NAME


ROUTER = APIRouter()


@ROUTER.post("/chat", response_model=ChatSessionResponse)
def chat(chat_session: ChatSessionRequest, request: Request) -> ChatSessionResponse:
    """Define the chat endpoint."""
    chats = chat_session.chats
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    chat_session = backend.get_tai_tutor_response(chats)
    return ChatSessionResponse.parse_obj(chat_session)


@ROUTER.post("/search", response_model=ResourceSearchAnswer)
def search(search_query: ResourceSearchQuery):
    """Define the search endpoint."""
    chats = search_query.chats
    chats.append(
        TaiSearchResponse(
            message="Here's some cool resources for you!",
            class_resource_snippets=[
                ClassResourceSnippet(
                    id=uuid4(),
                    class_id=uuid4(),
                    resource_snippet="Molecules are made up of atoms.",
                    full_resource_url="https://www.google.com",
                    preview_image_url="https://www.google.com",
                    metadata=Metadata(
                        title="Molecules",
                        description="Chemistry textbook snippet.",
                        tags=["molecules", "atoms"],
                        resource_type=ClassResourceType.TEXTBOOK,
                    ),
                ),
            ],
        ),
    )
    dummy_response = ResourceSearchAnswer(
        id=search_query.id,
        class_id=search_query.class_id,
        chats=chats,
    )
    return dummy_response
