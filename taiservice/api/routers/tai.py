"""Define the API endpoints for the AI responses."""
from enum import Enum
from fastapi import APIRouter
from pydantic import Field

# first imports are for local development, second imports are for deployment
try:
    from taiservice.api.routers.base_schema import BasePydanticModel
except ImportError:
    from base_schema import BasePydanticModel


ROUTER = APIRouter()


class ChatRole(str, Enum):
    """Define the built-in MongoDB roles."""

    TAI_TUTOR = "tai"
    USER = "user"


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

EXAMPLE_CHAT_SESSION = {
    "id": "1234",
    "chat": [
        {"message": "I'm stuck on this problem.", "role": "user"},
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
        {"message": "Thank you for your help!", "role": "user"},
    ],
}

class ChatSession(BasePydanticModel):
    """Define the request model for the chat endpoint."""

    id: str = Field(
        ...,
        description="The ID of the chat session.",
    )
    chat: list[Chat] = Field(
        ...,
        description="The chat session message history.",
    )

    class Config:
        """Define the configuration for the chat session."""

        schema_extra = {
            "examples": [
                EXAMPLE_CHAT_SESSION,
            ],
        }

@ROUTER.post("/chat", response_model=ChatSession)
def chat(chat_session: ChatSession):
    """Define the chat endpoint."""
    dummy_response = ChatSession(
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
    "chat": [
        {"message": "I'm looking for some resources on Python.", "role": "user"},
    ],
}

class ResourceSearchQuery(ChatSession):
    """Define the request model for the search endpoint."""

    chat: list[UserChat] = Field(
        ...,
        max_items=1,
        description="The search query from the user.",
    )

    class Config:
        """Define the configuration for the search query."""

        schema_extra = {
            "examples": [
                EXAMPLE_SEARCH_QUERY,
            ],
        }

@ROUTER.post("/search", response_model=ChatSession)
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
