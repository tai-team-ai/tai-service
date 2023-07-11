"""Define the schemas for the TAI endpoints."""
from enum import Enum
import copy
from uuid import uuid4, UUID
from typing import Optional, Union

from pydantic import Field, validator

try:
    from .class_resources_schema import BaseClassResource
    from .base_schema import BasePydanticModel, EXAMPLE_UUID
    from .class_resources_schema import BaseClassResource, ClassResourceType
except (ImportError, KeyError):
    from routers.class_resources_schema import BaseClassResource
    from routers.base_schema import BasePydanticModel, EXAMPLE_UUID
    from routers.class_resources_schema import BaseClassResource, ClassResourceType

class TaiTutorName(str, Enum):
    """Define the supported TAI tutors."""
    
    FIN = "fin"
    ALEX = "alex"


class ChatRole(str, Enum):
    """Define the built-in MongoDB roles."""

    TAI_TUTOR = "taiTutor"
    STUDENT = "student"
    FUNCTION = "function"


class ResponseTechnicalLevel(str, Enum):
    """Define the technical level of the response."""

    EXPLAIN_LIKE_IM_5 = "like5"
    EXPLAIN_LIKE_IM_IN_HIGH_SCHOOL = "likeHighSchool"
    EXPLAIN_LIKE_IM_IN_COLLEGE = "likeCollege"
    EXPLAIN_LIKE_IM_AN_EXPERT_IN_THE_FIELD = "likeExpertInTheField"

class ClassResourceSnippet(BaseClassResource):
    """Define the request model for the class resource snippet."""

    resource_snippet: str = Field(
        ...,
        description="The snippet of the class resource. This is analogous to Google search snippets.",
    )


class Chat(BasePydanticModel):
    """Define the model for the chat message."""
    role: ChatRole = Field(
        ...,
        description="The role of the creator of the chat message.",
    )
    message: Union[str, dict] = Field(
        ...,
        description="The contents of the chat message. You can send an empty string to get a response from the TAI tutor.",
    )
    render_chat: bool = Field(
        default=True,
        description="Whether or not to render the chat message. If false, the chat message will be hidden from the student.",
    )


class FunctionChat(Chat):
    """Define the model for the function chat message."""

    role: ChatRole = Field(
        default=ChatRole.FUNCTION,
        const=True,
        description="The role of the creator of the chat message.",
    )
    function_name: str = Field(
        ...,
        description="The name of the function that created the chat.",
    )
    render_chat: bool = Field(
        default=False,
        const=True,
        description="Whether or not to render the chat message. If false, the chat message will be hidden from the student.",
    )


class BaseStudentChat(Chat):
    """Define the base model for the student chat message."""
    role: ChatRole = Field(
        default=ChatRole.STUDENT,
        const=True,
        description="The role of the creator of the chat message.",
    )

class StudentChat(BaseStudentChat):
    """Define the model for the student chat message."""

    requested_tai_tutor: Optional[TaiTutorName] = Field(
        ...,
        description="The name of the TAI tutor to use in the response.",
    )
    requested_technical_level: Optional[ResponseTechnicalLevel] = Field(
        default=ResponseTechnicalLevel.EXPLAIN_LIKE_IM_IN_HIGH_SCHOOL,
        description="The technical level expected of the response.",
    )


class TaiTutorChat(Chat):
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
    class_resource_snippets: list[ClassResourceSnippet] = Field(
        ...,
        description="The class resources that were used to generate the response.",
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
    "id": EXAMPLE_UUID,
    "classId": EXAMPLE_UUID,
    "chats": [
        {
            "message": "I'm stuck on this problem.",
            "role": ChatRole.STUDENT,
            "requestedTaiTutor": TaiTutorName.ALEX,
            "requestedTechnicalLevel": ResponseTechnicalLevel.EXPLAIN_LIKE_IM_IN_HIGH_SCHOOL,
            "renderChat": True,
        },
    ],
}


EXAMPLE_CHAT_SESSION_RESPONSE = copy.deepcopy(EXAMPLE_CHAT_SESSION_REQUEST)
EXAMPLE_CLASS_RESOURCE_SNIPPET = {
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
}
EXAMPLE_CHAT_SESSION_RESPONSE["chats"].append(
    {
        "message": "I can help you with that!",
        "role": ChatRole.TAI_TUTOR,
        "taiTutor": TaiTutorName.ALEX,
        "technicalLevel": ResponseTechnicalLevel.EXPLAIN_LIKE_IM_IN_HIGH_SCHOOL,
        "classResourceSnippets": [
            copy.deepcopy(EXAMPLE_CLASS_RESOURCE_SNIPPET),
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
    def validate_student_is_last_chat(cls, chats: list[Chat]) -> list[Chat]:
        """Validate that the student is the last chat message."""
        if chats[-1].role != ChatRole.STUDENT:
            raise ValueError("The student must be the last chat message.")
        return chats


class ChatSessionResponse(BaseChatSession):
    """Define the response model for the chat endpoint."""

    chats: list[Union[StudentChat, TaiTutorChat, FunctionChat]] = Field(
        ...,
        description="The chat session message history.",
    )

    @validator("chats")
    def validate_tai_is_last_chat(cls, chats: list[Chat]) -> list[Chat]:
        """Validate that the TAI tutor is the last chat message."""
        if chats[-1].role != ChatRole.TAI_TUTOR:
            raise ValueError("The TAI tutor must be the last chat message.")
        return chats

    class Config:
        """Define the configuration for the chat session."""

        schema_extra = {
            "example": EXAMPLE_CHAT_SESSION_RESPONSE,
        }



EXAMPLE_SEARCH_QUERY = {
    "id": uuid4(),
    "classId": uuid4(),
    "query": "Python",
}
EXAMPLE_SEARCH_ANSWER = copy.deepcopy(EXAMPLE_SEARCH_QUERY)
EXAMPLE_SEARCH_ANSWER.update(
    {
        "summary_snippet": "Python is a programming language.",
        "suggested_resources": [
            copy.deepcopy(EXAMPLE_CLASS_RESOURCE_SNIPPET),
        ],
        "other_resources": [
            copy.deepcopy(EXAMPLE_CLASS_RESOURCE_SNIPPET),
        ],
    }
)


class SearchFilters(BasePydanticModel):
    """Define the search filters."""
    resource_types: list[ClassResourceType] = Field(
        default_factory=lambda: [resource_type for resource_type in ClassResourceType],
        description="The resource types to filter by.",
    )

class ResourceSearchQuery(BasePydanticModel):
    """Define the request model for the search endpoint."""
    id: UUID = Field(
        ...,
        description="The ID of the search.",
    )
    class_id: UUID = Field(
        ...,
        description="The ID of the class that the search is for.",
    )
    query: str = Field(
        ...,
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

class ResourceSearchAnswer(ResourceSearchQuery):
    """Define the response model for the search endpoint."""
    summary_snippet: str = Field(
        ...,
        description="The summary snippet of the search results.",
    )
    suggested_resources: list[ClassResourceSnippet] = Field(
        ...,
        description="The suggested resources that should appear at the top of the search results.",
    )
    other_resources: list[ClassResourceSnippet] = Field(
        ...,
        description="The other resources. These can be grouped by class resource type.",
    )

    class Config:
        """Define the configuration for the search answer."""
        schema_extra = {
            "example": EXAMPLE_SEARCH_ANSWER,
        }
