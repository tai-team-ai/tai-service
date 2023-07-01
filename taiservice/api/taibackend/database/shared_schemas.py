"""Define shared schemas for database models."""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ClassResourceType(str, Enum):
    """Define the built-in MongoDB roles."""

    # VIDEO = "video"
    # TEXT = "text"
    # IMAGE = "image"
    # AUDIO = "audio"
    PDF = "pdf"

class Metadata(BaseModel):
    """Define the metadata of the class resource."""

    title: str = Field(
        ...,
        description="The title of the class resource. This can be the file name or url if no title is provided.",
    )
    description: str = Field(
        ...,
        description="The description of the class resource.",
    )
    tags: list = Field(
        default_factory=list,
        description="The tags of the class resource.",
    )
    resource_type: str = Field(
        ...,
        description="The type of the class resource.",
    )
    total_page_count: Optional[int] = Field(
        default=None,
        description="The page count of the class resource.",
    )

class ChunkMetadata(Metadata):
    """Define the metadata of the class resource chunk."""

    class_id: str = Field(
        ...,
        description="The ID of the class that the resource belongs to.",
    )
    page_number: Optional[int] = Field(
        default=None,
        description="The page number of the class resource.",
    )
    time_stamp: Optional[int] = Field(
        default=None,
        description="The time stamp of the class resource.",
    )