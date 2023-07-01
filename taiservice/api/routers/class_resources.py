"""Define CRUD endpoints for class resources."""
from enum import Enum
from textwrap import dedent
from typing import Optional
from uuid import UUID, uuid4
from fastapi import APIRouter
from pydantic import Field, HttpUrl
try:
    from .base_schema import BasePydanticModel
    from ..taibackend.indexer.schemas import ClassResourceProcessingStatus
except ImportError:
    from routers.base_schema import BasePydanticModel
    from taibackend.indexer.schemas import ClassResourceProcessingStatus


ROUTER = APIRouter()

class ClassResourceType(str, Enum):
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
    resource_type: ClassResourceType = Field(
        ...,
        description=f"The type of the class resource. Valid values are: {', '.join([role.value for role in ClassResourceType])}",
    )

class BaseClassResource(BasePydanticModel):
    """Define the base model of the class resource."""

    id: UUID = Field(
        ...,
        description="The ID of the class resource.",
    )
    class_id: UUID = Field(
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

EXAMPLE_CLASS_RESOURCE = {
    # example pdf resource
    "id": uuid4(),
    "classId": uuid4(),
    "fullResourceUrl": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
    "previewImageUrl": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
    "metadata": {
        "title": "dummy.pdf",
        "description": "This is a dummy pdf file.",
        "tags": ["dummy", "pdf"],
        "resourceType": ClassResourceType.PDF,
    },
}

class ClassResource(BaseClassResource):
    """Define the complete model of the class resource."""

    status: Optional[ClassResourceProcessingStatus] = Field(
        default=None,
        description=f"The status of the class resource. Valid values are: {', '.join([status.value for status in ClassResourceProcessingStatus])}",
    )

    class Config:
        """Configure the Pydantic model."""

        schema_extra = {
            "example": EXAMPLE_CLASS_RESOURCE,
        }



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