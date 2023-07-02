"""Define shared schemas for database models."""
from datetime import datetime
from uuid import UUID
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, Extra


class ClassResourceType(str, Enum):
    """Define the built-in MongoDB roles."""

    # VIDEO = "video"
    # TEXT = "text"
    # IMAGE = "image"
    # AUDIO = "audio"
    PDF = "pdf"

class BasePydanticModel(BaseModel):
    """
    Define the base model of the Pydantic model.

    This model extends the default dict method to convert all objects to strs.
    This is useful when using python packages that expect a serializable dict.
    """

    def _recurse_and_convert(self, obj: dict) -> dict:
        """Recursively convert all objects to strs."""
        for key, value in obj.items():
            # recursively convert all objects to strs
            if isinstance(value, UUID):
                obj[key] = str(value)
            elif isinstance(value, Enum):
                obj[key] = value.value
            elif isinstance(value, datetime):
                obj[key] = value.isoformat()
            elif isinstance(value, dict):
                self._recurse_and_convert(value)
        return obj

    def dict(self, *args, **kwargs):
        """Convert all objects to strs."""
        super_result = super().dict(*args, **kwargs)
        return self._recurse_and_convert(super_result)

    class Config:
        """Define the configuration for the Pydantic model."""

        use_enum_values = True
        serializable_dict_values = True

class Metadata(BasePydanticModel):
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
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="The time stamp of the class resource.",
    )

    class Config:
        """Define the configuration for the Pydantic model."""

        extra = Extra.allow
