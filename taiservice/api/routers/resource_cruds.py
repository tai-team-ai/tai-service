"""Define CRUD endpoints for class resources."""
from enum import Enum
from fastapi import APIRouter
from pydantic import BaseModel, Field

ROUTER = APIRouter()

class ResourceType(str, Enum):
    """Define the built-in MongoDB roles."""

    # VIDEO = "video"
    # TEXT = "text"
    # IMAGE = "image"
    # AUDIO = "audio"
    PDF = "pdf"

class ClassResource(BaseModel):
    """Define the request model for the class resource."""
    id: str = Field(
        ...,
        description="The ID of the class resource.",
    )
    title: str = Field(
        default="",
        description="The title of the class resource.",
    )
    resource_type: ResourceType = Field(
        ...,
        description="The type of the class resource.",
    )
    url: str = Field(
        ...,
        description="The URL of the class resource. This is the url to the raw resource in s3.",
    )
    metadata: dict = Field(
        ...,
        description="The metadata of the class resource.",
    )

class ClassResources(BaseModel):
    """Define the request model for the class resources."""
    class_resources: list[ClassResource] = Field(
        ...,
        description="The class resources.",
    )

@ROUTER.get("/class_resources", response_model=ClassResource)
def get_class_resources():
    """Get all class resources."""
    pass