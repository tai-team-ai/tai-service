"""Define CRUD endpoints for class resources."""
from enum import Enum
from textwrap import dedent
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field, HttpUrl
try:
    from taiservice.api.routers.base_schema import BasePydanticModel
except ImportError:
    from routers.base_schema import BasePydanticModel

ROUTER = APIRouter()

class ResourceType(str, Enum):
    """Define the built-in MongoDB roles."""

    # VIDEO = "video"
    # TEXT = "text"
    # IMAGE = "image"
    # AUDIO = "audio"
    PDF = "pdf"

class Metadata(BasePydanticModel):
    """Define the metadata of the class resource."""

    title: str = Field(
        ...,
        description="The title of the class resource. This can be the file name or url if no title is provided.",
    )
    description: Optional[str] = Field(
        default=None,
        description="The description of the class resource.",
    )
    tags: list = Field(
        default_factory=list,
        description="The tags of the class resource.",
    )
    resource_type: ResourceType = Field(
        ...,
        description=f"The type of the class resource. Valid values are: {', '.join([role.value for role in ResourceType])}",
    )

#example of pdf resource in s3
EXAMPLE_CLASS_RESOURCE = {
    "id": "1",
    "class_id": "1",
    "full_resource_url": "https://tai-class-resources.s3.amazonaws.com/1/1/1.pdf",
    "preview_image_url": "https://tai-class-resources.s3.amazonaws.com/1/1/1.png",
    "metadata": {
        "title": "1.pdf",
        "description": "This is a pdf resource.",
        "tags": ["pdf", "resource"],
        "resource_type": "pdf",
    },
}


class ClassResource(BasePydanticModel):
    """Define the base model of the class resource."""

    id: str = Field(
        ...,
        description="The ID of the class resource.",
    )
    class_id: str = Field(
        ...,
        description="The ID of the class that the resource belongs to.",
    )
    full_resource_url: HttpUrl = Field(
        ...,
        description=dedent(
            """The URL of the class resource.
        
            #### NOTE:
            * If this is a physical resource, then this field should be the s3 URL of the resource.
            * If this is a website, then this field should be the URL of the website."""
        ),
    )
    preview_image_url: Optional[HttpUrl] = Field(
        default=None,
        description="The URL of the preview image of the class resource.",
    )
    metadata: Metadata = Field(
        default_factory=Metadata,
        description="The metadata of the class resource.",
    )


class ClassResources(BasePydanticModel):
    """Define the base model of the class resources."""

    class_resources: list[ClassResource] = Field(
        default_factory=list,
        description="The list of class resources.",
    )

    class Config:
        """Configure the Pydantic model."""

        schema_extra = {
            "example": {
                "class_resources": [EXAMPLE_CLASS_RESOURCE],
            },
        }

@ROUTER.get("/class_resources", response_model=ClassResources)
def get_class_resources():
    """Get all class resources."""
    dummy_class_resources = ClassResources(class_resources=[EXAMPLE_CLASS_RESOURCE])
    return dummy_class_resources

@ROUTER.post("/class_resources")
def create_class_resource(class_resource: ClassResource):
    """Create a class resource."""
    print(class_resource)
    return
