"""Define the API endpoints for the AI responses."""
import copy
from uuid import uuid4
from typing import Union
from fastapi import APIRouter, Request
from pydantic import Field, validator
try:
    from .tai_schemas import(
        Chat,
        BaseChatSession,
        TaiTutorName,
        TaiTutorChat,
        TaiSearchResponse,
        ChatRole,
        ResponseTechnicalLevel,
        ClassResourceSnippet,
        ChatSessionRequest,
        ChatSessionResponse,
    )
    from ..routers.base_schema import BasePydanticModel
    from ..routers.class_resources_schema import ClassResourceType, Metadata
    from ..taibackend.backend import Backend
    from ..runtime_settings import BACKEND_ATTRIBUTE_NAME
except ImportError:
    from routers.tai_schemas import (
        Chat,
        BaseChatSession,
        TaiTutorName,
        TaiTutorChat,
        TaiSearchResponse,
        ChatRole,
        ResponseTechnicalLevel,
        ClassResourceSnippet,
        ChatSessionRequest,
        ChatSessionResponse,
    )
    from routers.base_schema import BasePydanticModel
    from routers.class_resources_schema import ClassResourceType, Metadata
    from taibackend.backend import Backend
    from runtime_settings import BACKEND_ATTRIBUTE_NAME

ROUTER = APIRouter()


@ROUTER.post("/chat", response_model=ChatSessionResponse)
def chat(chat_session: ChatSessionRequest, request: Request) -> ChatSessionResponse:
    """Define the chat endpoint."""
    chats = chat_session.chats
    backend: Backend = getattr(request.app.state, BACKEND_ATTRIBUTE_NAME)
    class_snippets = backend.get_relevant_class_resources(chat_session.chats[-1].message, chat_session.class_id)
    chats.append(
        TaiTutorChat(
            message="I can help you with that!",
            role=ChatRole.TAI_TUTOR,
            tai_tutor=TaiTutorName.ALEX,
            technical_level=ResponseTechnicalLevel.EXPLAIN_LIKE_IM_IN_HIGH_SCHOOL,
            render_chat=True,
            class_resource_snippets=class_snippets,
        ),
    )
    return ChatSessionResponse.parse_obj(chat_session)


EXAMPLE_SEARCH_QUERY = {
    "id": uuid4(),
    "classId": uuid4(),
    "chats": [
        {
            "message": "I'm looking for some resources on Python.",
        },
    ],
}
EXAMPLE_SEARCH_ANSWER = copy.deepcopy(EXAMPLE_SEARCH_QUERY)
EXAMPLE_SEARCH_ANSWER["chats"].append(
    {
        "message": "Here are some resources on Python.",
        "classResourceSnippets": [
            {
                "id": uuid4(),
                "classId": uuid4(),
                "resourceSnippet": "Molecules are made up of atoms.",
                "fullResourceUrl": "https://www.google.com",
                "previewImageUrl": "https://www.google.com",
                "metadata": {
                    "title": "Molecules",
                    "description": "Molecules are made up of atoms.",
                    "tags": ["molecules", "atoms"],
                    "resourceType": ClassResourceType.TEXTBOOK
                },
            },
        ],
    },
)


class SearchFilters(BasePydanticModel):
    """Define the search filters."""

    resource_types: list[ClassResourceType] = Field(
        default_factory=lambda: [resource_type for resource_type in ClassResourceType],
        description="The resource types to filter by.",
    )

class ResourceSearchQuery(BaseChatSession):
    """
    Define the request model for the search endpoint.

    *NOTE:* This is identical to the chat session request model except that 
    this requires that only one student chat message is sent.
    """

    chats: list[Chat] = Field(
        ...,
        max_items=1,
        description="The search query from the student.",
    )
    filters: SearchFilters = Field(
        default_factory=SearchFilters,
        description="The search filters.",
    )

    class Config:
        """Define the configuration for the search query."""

        schema_extra = {
            "example": EXAMPLE_SEARCH_QUERY,
        }

class ResourceSearchAnswer(BaseChatSession):
    """Define the response model for the search endpoint."""

    chats: list[Union[Chat, TaiSearchResponse]] = Field(
        ...,
        description="The chat session message history.",
    )

    class Config:
        """Define the configuration for the search answer."""

        schema_extra = {
            "example": EXAMPLE_SEARCH_ANSWER,
        }

    @validator("chats")
    def validate_tai_is_last_chat(cls, chats: list[Union[Chat, TaiSearchResponse]]) -> list[Union[Chat, TaiSearchResponse]]:
        """Validate that the TAI tutor is the last chat message."""
        if isinstance(chats[-1], TaiSearchResponse):
            return chats
        raise ValueError("The TAI must be the last chat message for the search response.")


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
