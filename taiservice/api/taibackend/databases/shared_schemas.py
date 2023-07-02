"""Define shared schemas for database models."""
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
    This is parameterized by the Config class.
    """

    def dict(self, *args, **kwargs):
        """Convert all objects to strs."""
        super_result = super().dict(*args, **kwargs)
        if self.Config.serializable_dict_values:
            for key, value in super_result.items():
                super_result[key] = str(value)
        return super_result

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
    time_stamp: Optional[int] = Field(
        default=None,
        description="The time stamp of the class resource.",
    )

    class Config:
        """Define the configuration for the Pydantic model."""

        extra = Extra.allow
