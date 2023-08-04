"""Define shared schemas for database models."""
from datetime import datetime, timedelta
from uuid import UUID
from uuid import uuid4
from enum import Enum
from typing import Any, Optional
from pathlib import Path
from pydantic import BaseModel, Field, Extra, HttpUrl, constr


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

    def dict(self, *args, serialize_dates: bool = True, serialize_nums: bool = True, **kwargs):
        """Convert all objects to strs."""
        super_result = super().dict(*args, **kwargs)
        types_to_serialize = (UUID, Enum, Path)
        if serialize_nums:
            types_to_serialize += (int, float)
        if serialize_dates:
            types_to_serialize += (datetime,)
        result = self._recurse_and_serialize(super_result, types_to_serialize)
        return result

    class Config:
        """Define the configuration for the Pydantic model."""

        use_enum_values = True
        allow_population_by_field_name = True


class DateRange(BasePydanticModel):
    """Define a schema for a date range."""
    start_date: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(days=7),
        description="The start date of the date range.",
    )
    end_date: datetime = Field(
        default_factory=datetime.utcnow,
        description="The end date of the date range.",
    )


class UsageMetric(BasePydanticModel):
    """Define the usage log model for tracking usage of resources."""
    timestamp: datetime = Field(
        ...,
        description="The date of the usage metric.",
    )


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
    vector_id: UUID = Field(
        default_factory=uuid4,
        description="The ID of the class resource chunk vector.",
    )
    chunk_id: Optional[UUID] = Field(
        default=None,
        description="The ID of the class resource chunk.",
    )

    class Config:
        """Define the configuration for the model."""

        extra = Extra.allow

class BaseClassResourceDocument(BasePydanticModel):
    """Define the base model of the class resource."""
    id: UUID = Field(
        ...,
        description="The ID of the class resource.",
        alias="_id",
    )
    class_id: UUID = Field(
        ...,
        description="The ID of the class that the resource belongs to.",
    )
    full_resource_url: HttpUrl = Field(
        ...,
        description="The URL of the class resource.",
    )
    preview_image_url: Optional[HttpUrl] = Field(
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
    usage_log: list[UsageMetric] = Field(
        default_factory=list,
        description="The usage log of the class resource. This allows us to track the usage of the resource.",
    )

    @property
    def id_as_str(self) -> str:
        """Return the string representation of the id."""
        return str(self.id)

    def dict(self, *args, **kwargs) -> dict:
        """Convert all objects to strs."""
        self.modified_timestamp = datetime.utcnow()
        return super().dict(*args, **kwargs)


class StatefulClassResourceDocument(BaseClassResourceDocument):
    """Define the stateful class resource document."""
    hashed_document_contents: constr(min_length=40, max_length=40) = Field(
        ...,
        description=("This field serves as a version/revision number for the document. "
            "It is used to determine if the document has changed since the last time "
            "it was processed. The value of this field is the SHA1 hash of the document "
            "contents."
        )
    )


class BaseOpenAIConfig(BaseModel):
    """Define the base OpenAI config."""
    api_key: str = Field(
        ...,
        description="The API key of the OpenAI API.",
    )
    request_timeout: int = Field(
        default=30,
        le=60,
        description="The timeout for requests to the OpenAI API.",
    )
