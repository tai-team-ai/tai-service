"""Define the API endpoints for the AI responses."""
import copy
import sys
from uuid import uuid4, UUID
from enum import Enum
from typing import Optional, Union
from fastapi import APIRouter
from pydantic import Field, validator
try:
    from ..taibackend.shared_schemas import TaiTutorName
    from ..routers.base_schema import BasePydanticModel
    from ..routers.class_resources import BaseClassResource, ClassResourceType, Metadata
except ImportError:
    from taibackend.shared_schemas import TaiTutorName
    from routers.base_schema import BasePydanticModel
    from routers.class_resources import BaseClassResource, ClassResourceType, Metadata

ROUTER = APIRouter()

class ChatRole(str, Enum):
    """Define the built-in MongoDB roles."""

    TAI_TUTOR = "tai_tutor"
    STUDENT = "student"


class ResponseTechnicalLevel(str, Enum):
    """Define the technical level of the response."""

    EXPLAIN_LIKE_IM_5 = "explain_like_im_5"
    EXPLAIN_LIKE_IM_IN_HIGH_SCHOOL = "explain_like_im_in_high_school"
    EXPLAIN_LIKE_IM_IN_COLLEGE = "explain_like_im_in_college"
    EXPLAIN_LIKE_IM_AN_EXPERT_IN_THE_FIELD = "explain_like_im_an_expert_in_the_field"


class ClassResourceSnippet(BaseClassResource):
    """Define the request model for the class resource snippet."""

    resource_snippet: str = Field(
        ...,
        description="The snippet of the class resource. This is analogous to Google search snippets.",
    )


class Chat(BasePydanticModel):
    """Define the model for the chat message."""

    message: str = Field(
        ...,
        description="The contents of the chat message. You can send an empty string to get a response from the TAI tutor.",
    )
    render_chat: bool = Field(
        default=True,
        description="Whether or not to render the chat message. If false, the chat message will be hidden from the student.",
    )


class StudentChat(Chat):
    """Define the model for the student chat message."""

    role: ChatRole = Field(
        default=ChatRole.STUDENT,
        const=True,
        description="The role of the creator of the chat message.",
    )
    requested_tai_tutor: Optional[TaiTutorName] = Field(
        ...,
        description="The name of the TAI tutor to use in the response.",
    )
    requested_technical_level: Optional[ResponseTechnicalLevel] = Field(
        default=ResponseTechnicalLevel.EXPLAIN_LIKE_IM_IN_HIGH_SCHOOL,
        description="The technical level expected of the response.",
    )


class TaiSearchResponse(Chat):
    """Define the model for the TAI chat message."""

    class_resource_snippets: list[ClassResourceSnippet] = Field(
        ...,
        description="The class resources that were used to generate the response.",
    )

class TaiTutorChat(TaiSearchResponse):
    """Define the model for the TAI Tutor chat message."""

    role: ChatRole = Field(
        default=ChatRole.TAI_TUTOR,
        const=True,
        description="The role of the creator of the chat message.",
    )
    tai_tutor: TaiTutorName = Field(
        ...,
        description="The name of the TAI tutor that generated the response.",
    )
    technical_level: ResponseTechnicalLevel = Field(
        ...,
        description="The technical level of the response.",
    )

class BaseChatSession(BasePydanticModel):
    """Define the request model for the chat endpoint."""

    id: UUID = Field(
        ...,
        description="The ID of the chat session.",
    )
    class_id: UUID = Field(
        ...,
        description="The ID of the class that the chat session is for.",
    )
    chats: list[Chat] = Field(
        ...,
        description="The chat session message history.",
    )

EXAMPLE_CHAT_SESSION_REQUEST = {
    "id": uuid4(),
    "classId": uuid4(),
    "chats": [
        {
            "message": "I'm stuck on this problem.",
            "role": "student",
            "requestedTaiTutor": TaiTutorName.ALEX,
            "requestedTechnicalLevel": ResponseTechnicalLevel.EXPLAIN_LIKE_IM_IN_HIGH_SCHOOL,
            "renderChat": True,
        },
    ],
}


EXAMPLE_CHAT_SESSION_RESPONSE = copy.deepcopy(EXAMPLE_CHAT_SESSION_REQUEST)
EXAMPLE_CHAT_SESSION_RESPONSE["chats"].append(
    {
        "message": "I can help you with that!",
        "role": "tai_tutor",
        "taiTutor": TaiTutorName.ALEX,
        "technicalLevel": ResponseTechnicalLevel.EXPLAIN_LIKE_IM_IN_HIGH_SCHOOL,
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
                    "resourceType": "pdf",
                },
            },
        ],
        "renderChat": True,
    },
)

class ChatSessionRequest(BaseChatSession):
    """Define the request model for the chat endpoint."""

    chats: list[Union[StudentChat, TaiTutorChat]] = Field(
        ...,
        description="The chat session message history.",
    )

    class Config:
        """Define the configuration for the chat session."""

        schema_extra = {
            "example": EXAMPLE_CHAT_SESSION_REQUEST,
        }

    @validator("chats")
    def validate_student_is_last_chat(cls, chats: list[Union[StudentChat, TaiSearchResponse]]) -> list[Union[StudentChat, TaiSearchResponse]]:
        """Validate that the student is the last chat message."""
        if chats[-1].role != ChatRole.STUDENT:
            raise ValueError("The student must be the last chat message.")
        return chats


class ChatSessionResponse(BaseChatSession):
    """Define the response model for the chat endpoint."""

    chats: list[Union[StudentChat, TaiTutorChat]] = Field(
        ...,
        description="The chat session message history.",
    )

    @validator("chats")
    def validate_tai_is_last_chat(cls, chats: list[Union[StudentChat, TaiTutorChat]]) -> list[Union[StudentChat, TaiTutorChat]]:
        """Validate that the TAI tutor is the last chat message."""
        if chats[-1].role != ChatRole.TAI_TUTOR:
            raise ValueError("The TAI tutor must be the last chat message.")
        return chats

    class Config:
        """Define the configuration for the chat session."""

        schema_extra = {
            "example": EXAMPLE_CHAT_SESSION_RESPONSE,
        }


@ROUTER.post("/chat", response_model=ChatSessionResponse)
def chat(chat_session: ChatSessionRequest):
    """Define the chat endpoint."""
    chats = chat_session.chats
    chats.append(
        TaiTutorChat(
            message="I can help you with that!",
            role=ChatRole.TAI_TUTOR,
            tai_tutor=TaiTutorName.ALEX,
            technical_level=ResponseTechnicalLevel.EXPLAIN_LIKE_IM_IN_HIGH_SCHOOL,
            render_chat=True,
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
                        resource_type=ClassResourceType.PDF,
                    )
                ),
            ],
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
                    "resourceType": "pdf",
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
                        resource_type=ClassResourceType.PDF,
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
