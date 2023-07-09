"""Define the schema for the class resource endpoints."""
from enum import Enum
from textwrap import dedent
from typing import Optional, Annotated
from uuid import UUID
from pydantic import Field, HttpUrl
from fastapi import Query
# first imports are for local development, second imports are for deployment
try:
    from ..routers.base_schema import BasePydanticModel, EXAMPLE_UUID
except ImportError:
    from routers.base_schema import BasePydanticModel, EXAMPLE_UUID


ClassResourceIds = Annotated[list[UUID] | None, Query()]

class ClassResourceProcessingStatus(str, Enum):
    """Define the processing status of the class resource."""
    PENDING = "pending"
    PROCESSING = "processing"
    DELETING = "deleting"
    FAILED = "failed"
    COMPLETED = "completed"


class ClassResourceType(str, Enum):
    """Define the type of the class resource."""
    TEXTBOOK = "textbook"
    WEBSITE = "website"


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
    "id": EXAMPLE_UUID,
    "classId": EXAMPLE_UUID,
    "fullResourceUrl": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
    "previewImageUrl": "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
    "status": ClassResourceProcessingStatus.PROCESSING,
    "metadata": {
        "title": "dummy.pdf",
        "description": "This is a dummy pdf file.",
        "tags": ["dummy", "pdf"],
        "resourceType": ClassResourceType.TEXTBOOK,
    },
}

class ClassResource(BaseClassResource):
    """Define the complete model of the class resource."""
    status: ClassResourceProcessingStatus = Field(
        ...,
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

