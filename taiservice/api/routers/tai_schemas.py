"""Define the schemas for the TAI endpoints."""
from enum import Enum
import copy
from textwrap import dedent
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

    MILO = "Milo"
    DECLAN = "Declan"
    FINN = "Finn"
    ADA = "Ada"
    REMY = "Remy"
    KAI = "Kai"
    VIOLET = "Violet"


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
    raw_snippet_url: str = Field(
        ...,
        description="The url of the raw snippet of the class resource.",
    )
    rank: int = Field(
        default=0,
        description="The rank of the class resource snippet.",
    )
    relevance_score: float = Field(
        default=0.0,
        description="The relevance score of the class resource snippet.",
    )

    @property
    def simplified_string(self) -> str:
        """Return the simplified schema."""
        simplified_schema = dedent(f"""\
        Title:
            {self.metadata.title}
        Resource Snippet:
            {self.resource_snippet}
        Resource Type:
            {self.metadata.resource_type}
        """)
        return str(simplified_schema)


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


class AIResponseCallingFunction(BasePydanticModel):
    """Define the model for the AI response calling function."""

    name: str = Field(
        ...,
        description="The name of the function to call.",
    )
    arguments: dict = Field(
        ...,
        description="The arguments to pass to the function.",
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
    function_call: Optional[AIResponseCallingFunction] = Field(
        default=None,
        description="The function call that the assistant wants to make.",
    )


class BaseChatSession(BasePydanticModel):
    """Define the request model for the chat endpoint."""

    id: UUID = Field(
        ...,
        description="The ID of the chat session.",
    )
    # TODO: need ot make this required once BE is updated
    user_id: Optional[UUID] = Field(
        default_factory=uuid4,
        description="The ID of the user that the chat session is for.",
    )
    class_id: UUID = Field(
        ...,
        description="The ID of the class that the chat session is for.",
    )
    class_name: str = Field(
        ...,
        max_length=100,
        min_length=1,
        description="The name of the class that the chat session is for.",
    )
    class_description: str = Field(
        ...,
        max_length=400,
        min_length=1,
        description="The description of the course that the chat session is for.",
    )
    chats: list[Chat] = Field(
        ...,
        description="The chat session message history.",
    )

EXAMPLE_CHAT_SESSION_REQUEST = {
    "id": EXAMPLE_UUID,
    "userId": EXAMPLE_UUID,
    "classId": EXAMPLE_UUID,
    "className": "Intro to Python",
    "classDescription": "Learn the basics of Python in a fun class.",
    "chats": [
        {
            "message": "I'm stuck on this problem about dummy pdfs.",
            "role": ChatRole.STUDENT,
            "requestedTaiTutor": TaiTutorName.ADA,
            "requestedTechnicalLevel": ResponseTechnicalLevel.EXPLAIN_LIKE_IM_IN_HIGH_SCHOOL,
            "renderChat": True,
        },
    ],
}


EXAMPLE_CHAT_SESSION_RESPONSE = copy.deepcopy(EXAMPLE_CHAT_SESSION_REQUEST)
EXAMPLE_CLASS_RESOURCE_SNIPPET = {
    "id": EXAMPLE_UUID,
    "classId": EXAMPLE_UUID,
    "resourceSnippet": "Molecules are made up of atoms.",
    "fullResourceUrl": "https://www.google.com",
    "previewImageUrl": "https://www.google.com",
    "rawSnippetUrl": "https://www.google.com",
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
        "taiTutor": TaiTutorName.ADA,
        "technicalLevel": ResponseTechnicalLevel.EXPLAIN_LIKE_IM_IN_HIGH_SCHOOL,
        "classResourceSnippets": [
            copy.deepcopy(EXAMPLE_CLASS_RESOURCE_SNIPPET),
        ],
        "renderChat": True,
    },
)

class ChatSessionRequest(BaseChatSession):
    """Define the request model for the chat endpoint."""
    chats: list[Union[StudentChat, TaiTutorChat, FunctionChat]] = Field(
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
    "classId": EXAMPLE_UUID,
    "query": "dummy pdf",
    "userId": EXAMPLE_UUID,
}
EXAMPLE_RESOURCE_SEARCH_QUERY = copy.deepcopy(EXAMPLE_SEARCH_QUERY)
EXAMPLE_RESOURCE_SEARCH_QUERY.update(
    {
        "filters": {
            "resourceTypes": [
                ClassResourceType.TEXTBOOK,
            ],
        },
    }
)
EXAMPLE_BASE_SEARCH_RESPONSE = copy.deepcopy(EXAMPLE_SEARCH_QUERY)
EXAMPLE_BASE_SEARCH_RESPONSE.update(
    {
        "suggestedResources": [
            copy.deepcopy(EXAMPLE_CLASS_RESOURCE_SNIPPET),
        ],
        "otherResources": [
            copy.deepcopy(EXAMPLE_CLASS_RESOURCE_SNIPPET),
        ],
    }
)
EXAMPLE_SEARCH_ANSWER = copy.deepcopy(EXAMPLE_BASE_SEARCH_RESPONSE)
EXAMPLE_SEARCH_ANSWER.update(
    {
        "summary_snippet": "Python is a programming language.",
    }
)


class SearchFilters(BasePydanticModel):
    """Define the search filters."""
    resource_types: list[ClassResourceType] = Field(
        default_factory=lambda: [resource_type for resource_type in ClassResourceType],
        description="The resource types to filter by.",
    )


class SearchQuery(BasePydanticModel):
    """Define the request model for the search endpoint."""
    id: UUID = Field(
        default_factory=uuid4,
        description="The ID of the search.",
    )
    # TODO: need ot make this required once BE is updated
    user_id: Optional[UUID] = Field(
        default_factory=uuid4,
        description="The ID of the user that the search is for.",
    )
    class_id: UUID = Field(
        ...,
        description="The ID of the class that the search is for.",
    )
    query: str = Field(
        ...,
        description="The search query from the student.",
    )

    class Config:
        """Define the configuration for the search query."""
        schema_extra = {
            "example": EXAMPLE_SEARCH_QUERY,
        }


class ResourceSearchQuery(SearchQuery):
    """Define the request model for the resource search endpoint."""

    filters: SearchFilters = Field(
        default_factory=SearchFilters,
        description="The search filters.",
    )

    class Config:
        """Define the configuration for the search query."""
        schema_extra = {
            "example": EXAMPLE_RESOURCE_SEARCH_QUERY,
        }


class SearchResults(ResourceSearchQuery):
    """Define the response model for the search endpoint."""
    suggested_resources: list[ClassResourceSnippet] = Field(
        ...,
        description="The suggested resources that should appear at the top of the search results.",
    )
    other_resources: list[ClassResourceSnippet] = Field(
        ...,
        description="The other resources. These can be grouped by class resource type.",
    )

    class Config:
        """Define the configuration for the search response."""
        schema_extra = {
            "example": EXAMPLE_BASE_SEARCH_RESPONSE,
        }
