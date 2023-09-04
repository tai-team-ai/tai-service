"""Define shared schemas for database models."""
from datetime import datetime, timedelta
from hashlib import sha1
from uuid import UUID
from uuid import uuid4
from enum import Enum
from typing import Any, Optional, Union
from pathlib import Path
from pydantic import BaseModel, Field, Extra, HttpUrl, root_validator


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
    """Define the type of the class resource."""
    TEXTBOOK = "textbook"
    EXAMPLE_PROBLEMS = "example problems"
    STUDY_GUIDE = "study guide"
    LECTURE = "lecture"
    ARTICLE = "article"


class ClassResourceProcessingStatus(str, Enum):
    """Define the document status."""
    PENDING = "pending"
    PROCESSING = "processing"
    FAILED = "failed"
    DELETING = "deleting"
    COMPLETED = "completed"


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

    def dict(self, *, serialize_dates: bool = False, serialize_nums: bool = False, **kwargs):
        """Convert all objects to strs."""
        super_result = super().dict(**kwargs)
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
        validate_assignment = True
        arbitrary_types_allowed = True


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
    page_number: int = Field(
        default=1,
        description="The page number of the class resource.",
    )
    total_page_count: int = Field(
        default=1,
        description="The page count of the class resource.",
    )

    class Config:
        """Define the configuration for the model."""

        extra = Extra.allow


class ChunkSize(str, Enum):
    """Define the chunk size."""
    SMALL = "small"
    LARGE = "large"


class ChunkMetadata(Metadata):
    """Define the metadata of the class resource chunk."""

    class_id: UUID = Field(
        ...,
        description="The ID of the class that the resource belongs to.",
    )
    vector_id: UUID = Field(
        default_factory=uuid4,
        description="The ID of the class resource chunk vector.",
    )
    chunk_id: Optional[UUID] = Field(
        default=None,
        description="The ID of the class resource chunk.",
    )
    sections: list[str] = Field(
        default_factory=list,
        description="The sections associated with the class resource chunk.",
    )
    chapters: list[str] = Field(
        default_factory=list,
        description="The chapters associated with the class resource chunk.",
    )
    chunk_size: ChunkSize = Field(
        ...,
        description="The size of the class resource chunk. Smaller provides more granularity.",
    )

    class Config:
        """Define the configuration for the model."""

        extra = Extra.allow

class BaseClassResourceDocument(BasePydanticModel):
    """Define the base model of the class resource."""
    id: UUID = Field(
        ...,
        description="The id of the class resource.",
        alias="_id",
    )
    class_id: UUID = Field(
        ...,
        description="The id of the class.",
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

    def dict(self, **kwargs) -> dict:
        """Convert all objects to strs."""
        self.modified_timestamp = datetime.utcnow()
        return super().dict(**kwargs)


class StatefulClassResourceDocument(BaseClassResourceDocument):
    """Define the stateful class resource document."""
    hashed_document_contents: str = Field(
        ...,
        min_length=40,
        max_length=40,
        description=("This field serves as a version/revision number for the document. "
            "It is used to determine if the document has changed since the last time "
            "it was processed. The value of this field is the SHA1 hash of the document "
            "contents."
        )
    )
    data_pointer: Union[HttpUrl, str, Path] = Field(
        ...,
        description=(
            "This field should 'point' to the data. This will mean different things "
            "depending on the input format and loading strategy. For example, if the input format "
            "is PDF and the loading strategy is PyMuPDF, then this field will be a path object, as another "
            "example, if the loading strategy is copy and paste, then this field will be a string."
        ),
    )
    status: ClassResourceProcessingStatus = Field(
        default=ClassResourceProcessingStatus.PENDING,
        description="The status of the class resource.",
    )

    @root_validator(pre=True)
    def generate_hashed_content_id(cls, values: dict) -> dict:
        """Generate the hashed content id."""
        data_pointer = values.get("data_pointer")
        if isinstance(data_pointer, Path):
            hashed_document_contents = sha1(data_pointer.read_bytes()).hexdigest()
        elif isinstance(data_pointer, HttpUrl):
            url = data_pointer.split("?")[0]
            hashed_document_contents = sha1(url.encode()).hexdigest()
        elif isinstance(data_pointer, str):
            hashed_document_contents = sha1(data_pointer.encode()).hexdigest()
        else:
            raise ValueError("The data pointer must be a path, string, or url.")
        values["hashed_document_contents"] = hashed_document_contents
        return values

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
