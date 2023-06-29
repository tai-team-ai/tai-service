"""Define the API endpoints for the AI responses."""
import copy
from textwrap import dedent
from enum import Enum
from typing import Optional, Union
from fastapi import APIRouter
from pydantic import Field, validator

# first imports are for local development, second imports are for deployment
try:
    from taiservice.api.taillm.schemas import TaiTutorName
    from taiservice.api.routers.base_schema import BasePydanticModel
except ImportError:
    from api.taillm.schemas import TaiTutorName
    from api.routers.base_schema import BasePydanticModel


ROUTER = APIRouter()


class ChatRole(str, Enum):
    """Define the built-in MongoDB roles."""

    TAI_TUTOR = "tai"
    USER = "user"


class ResponseTechnicalLevel(str, Enum):
    """Define the technical level of the response."""

    EXPLAIN_LIKE_IM_5 = "explain_like_im_5"
    EXPLAIN_LIKE_IM_IN_HIGH_SCHOOL = "explain_like_im_in_high_school"
    EXPLAIN_LIKE_IM_IN_COLLEGE = "explain_like_im_in_college"
    EXPLAIN_LIKE_IM_AN_EXPERT_IN_THE_FIELD = "explain_like_im_an_expert_in_the_field"


class ClassResourceSnippet(BasePydanticModel):
    """Define the request model for the class resource snippet."""

    resource_id: str = Field(
        ...,
        description="The ID of the class resource.",
    )
    resource_title: str = Field(
        ...,
        description="The title of the class resource.",
    )
    resource_snippet: str = Field(
        ...,
        description="The snippet of the class resource. This is analogous to Google search snippets.",
    )
    resource_preview_image_url: str = Field(
        ...,
        description="The URL of the class resource preview image.",
    )
    full_resource_url: str = Field(
        ...,
        description="The URL of the class resource. This is the url to the raw resource in s3.",
    )


class Chat(BasePydanticModel):
    """Define the model for the chat message."""

    message: str = Field(
        ...,
        description="The contents of the chat message. You can send an empty string to get a response from the TAI tutor.",
    )
    role: ChatRole = Field(
        ...,
        description="The role of the creator of the chat message.",
    )


class UserChat(Chat):
    """Define the model for the user chat message."""

    role: ChatRole = Field(
        default=ChatRole.USER,
        const=True,
        description="The role of the creator of the chat message.",
    )


class TaiChat(Chat):
    """Define the model for the TAI chat message."""

    role: ChatRole = Field(
        default=ChatRole.TAI_TUTOR,
        const=True,
        description="The role of the creator of the chat message.",
    )
    class_resources: list[ClassResourceSnippet] = Field(
        ...,
        description="The class resources that were used to generate the response.",
    )
    render_chat: bool = Field(
        ...,
        description="Whether or not to render the chat message. If false, the chat message will be hidden from the user.",
    )


EXAMPLE_CHAT_SESSION_USER_REQUEST = {
    "id": "1234",
    "chats": [
        {"message": "I'm stuck on this problem.", "role": "user"},
    ],
}
EXAMPLE_CHAT_SESSION_TAI_RESPONSE = copy.deepcopy(EXAMPLE_CHAT_SESSION_USER_REQUEST)
EXAMPLE_CHAT_SESSION_TAI_RESPONSE["chats"].append(
    {
        "message": "I can help you with that!",
        "role": "tai",
        "classResources": [
            {
                "resourceId": "123",
                "resourceTitle": "Hello World",
                "resourceSnippet": "Hello World",
                "resourcePreviewImageUrl": "https://www.google.com",
                "fullResourceUrl": "https://www.google.com",
            }
        ],
        "renderChat": True,
    },
)


class ChatSession(BasePydanticModel):
    """Define the request model for the chat endpoint."""

    id: str = Field(
        ...,
        description="The ID of the chat session.",
    )
    chats: list[Union[UserChat, TaiChat]] = Field(
        ...,
        description="The chat session message history.",
    )



class ChatSessionRequest(ChatSession):
    """Define the request model for the chat endpoint."""

    tai_tutor_name: TaiTutorName = Field(
        ...,
        description="The name of the TAI tutor.",
    )
    technical_level: Optional[ResponseTechnicalLevel] = Field(
        default=None,
        description="The technical level of the response.",
    )

    @validator("chats")
    def validate_user_is_last_chat(cls, chats: list[Union[UserChat, TaiChat]]) -> list[Union[UserChat, TaiChat]]:
        """Validate that the user is the last chat message."""
        if chats[-1].role != ChatRole.USER:
            raise ValueError("The user must be the last chat message.")
        return chats

    class Config:
        """Define the configuration for the chat session."""

        schema_extra = {
            "example": EXAMPLE_CHAT_SESSION_USER_REQUEST,
        }


class ChatSessionResponse(ChatSession):
    """Define the response model for the chat endpoint."""

    @validator("chats")
    def validate_tai_is_last_chat(cls, chats: list[Union[UserChat, TaiChat]]) -> list[Union[UserChat, TaiChat]]:
        """Validate that the TAI tutor is the last chat message."""
        if chats[-1].role != ChatRole.TAI_TUTOR:
            raise ValueError("The TAI tutor must be the last chat message.")
        return chats

    class Config:
        """Define the configuration for the chat session."""

        schema_extra = {
            "example": EXAMPLE_CHAT_SESSION_TAI_RESPONSE,
        }


@ROUTER.post("/chat", response_model=ChatSessionResponse)
def chat(chat_session: ChatSessionRequest):
    """Define the chat endpoint."""
    dummy_response = ChatSessionResponse(
        chat_session_id=chat_session.id,
        chat=[
            UserChat(
                message="I'm stuck on this problem.",
            ),
            TaiChat(
                message="I can help you with that!",
                class_resources=[
                    ClassResourceSnippet(
                        resource_id="123",
                        resource_title="Hello World",
                        resource_snippet="Hello World",
                        resource_preview_image_url="https://www.google.com",
                        full_resource_url="https://www.google.com",
                    )
                ],
            ),
        ],
    )
    return dummy_response


EXAMPLE_SEARCH_QUERY = {
    "id": "1234",
    "chats": [
        {"message": "I'm looking for some resources on Python.", "role": "user"},
    ],
}


class ResourceSearchQuery(ChatSession):
    dedent("""
    Define the request model for the search endpoint.

    *NOTE:* This is identical to the chat session request model except that 
    this requires that only one user chat message is sent.
    """)

    chats: list[UserChat] = Field(
        ...,
        max_items=1,
        description="The search query from the user.",
    )

    class Config:
        """Define the configuration for the search query."""

        schema_extra = {
            "example": EXAMPLE_SEARCH_QUERY,
        }


@ROUTER.post("/search", response_model=ChatSessionResponse)
def search(search_query: ResourceSearchQuery):
    """Define the search endpoint."""
    dummy_response = ChatSession(
        chat_session_id=search_query.id,
        chat=[
            UserChat(
                message="Hi TAI, I'm looking for some resources on Python.",
            ),
            TaiChat(
                message="Here's some cool resources for you!",
                class_resources=[
                    ClassResourceSnippet(
                        resource_id="123",
                        resource_title="Hello World",
                        resource_snippet="Hello World",
                        resource_preview_image_url="https://www.google.com",
                        full_resource_url="https://www.google.com",
                    )
                ],
            ),
        ],
    )
    return dummy_response
