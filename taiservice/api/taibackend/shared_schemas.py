"""Define shared schemas for database models."""
from datetime import datetime
from uuid import UUID
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, Extra, HttpUrl, validator


HASH_FIELD_OBJECT = Field(
    ...,
    le=40,
    ge=40,
    description=("This field serves as a version/revision number for the document. "
        "It is used to determine if the document has changed since the last time "
        "it was processed. The value of this field is the SHA1 hash of the document "
        "contents."
    )
)

class ClassResourceType(str, Enum):
    """Define the class resource types to use as a filter."""
    TEXTBOOK = "textbook"
    WEBSITE = "website"

class BasePydanticModel(BaseModel):
    """
    Define the base model of the Pydantic model.

    This model extends the default dict method to convert all objects to strs.
    This is useful when using python packages that expect a serializable dict.
    """

    def _recurse_and_serialize(self, obj: Any, types_to_serialize: tuple) -> Any:
        """Recursively convert all objects to strs."""
        def serialize(v):
            if isinstance(v, types_to_serialize):
                return str(v)
            return v
        if isinstance(obj, dict):
            obj = {k: self._recurse_and_serialize(v, types_to_serialize) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            obj = [self._recurse_and_serialize(v, types_to_serialize) for v in obj]
        else:
            obj = serialize(obj)
        return obj

    def dict(self, *args, serialize_dates: bool = True, **kwargs):
        """Convert all objects to strs."""
        super_result = super().dict(*args, **kwargs)
        types_to_serialize = (UUID, Enum)
        if serialize_dates:
            types_to_serialize += (datetime,)
        result = self._recurse_and_serialize(super_result, types_to_serialize)
        return result

    class Config:
        """Define the configuration for the Pydantic model."""

        use_enum_values = True


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
    resource_type: ClassResourceType = Field(
        ...,
        description="The type of the class resource.",
    )
    total_page_count: Optional[int] = Field(
        default=None,
        description="The page count of the class resource.",
    )

    class Config:
        """Define the configuration for the model."""

        extra = Extra.allow

class ChunkMetadata(Metadata):
    """Define the metadata of the class resource chunk."""

    class_id: UUID = Field(
        ...,
        description="The ID of the class that the resource belongs to.",
    )
    page_number: Optional[int] = Field(
        default=None,
        description="The page number of the class resource.",
    )

    class Config:
        """Define the configuration for the model."""

        extra = Extra.allow

class BaseClassResourceDocument(BasePydanticModel):
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
        description="The URL of the class resource.",
    )
    preview_image_url: Optional[str] = Field(
        default=None,
        description="The URL of the image preview of the class resource.",
    )
    metadata: Metadata = Field(
        ...,
        description="The metadata of the class resource.",
    )
    create_timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="The timestamp when the class resource was created.",
    )
    modified_timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="The timestamp when the class resource was last modified.",
    )

    @validator("modified_timestamp", pre=True)
    def set_modified_timestamp(cls, _: datetime) -> datetime:
        """Set the modified timestamp."""
        return datetime.utcnow()

    @property
    def str_id(self) -> str:
        """Return the string representation of the id."""
        return str(self.id)