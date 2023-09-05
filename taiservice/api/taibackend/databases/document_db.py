"""Define the pinecone database."""
from pathlib import Path
from datetime import datetime, timedelta
from enum import Enum
from typing import Union, Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field, Extra, HttpUrl
from pymongo import MongoClient
# first imports are for local dev, second for deployment
try:
    from ..shared_schemas import BasePydanticModel
except ImportError:
    from taibackend.shared_schemas import BasePydanticModel


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


class ClassResourceDocument(BasePydanticModel):
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
    status: ClassResourceProcessingStatus = Field(
        default=ClassResourceProcessingStatus.PENDING,
        description="The status of the class resource.",
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

    class Config:
        """Define the configuration for the model."""
        extra = Extra.allow

    @property
    def id_as_str(self) -> str:
        """Return the string representation of the id."""
        return str(self.id)

    def dict(self, *args, **kwargs) -> dict:
        """Convert all objects to strs."""
        self.modified_timestamp = datetime.utcnow()
        return super().dict(**kwargs)



class DocumentDBConfig(BaseModel):
    """Define the document database config."""
    username: str = Field(
        ...,
        description="The username of the document db.",
    )
    password: str = Field(
        ...,
        description="The password of the document db.",
    )
    fully_qualified_domain_name: str = Field(
        ...,
        description="The fully qualified domain name of the document db.",
    )
    port: int = Field(
        ...,
        description="The port of the document db.",
    )
    database_name: str = Field(
        ...,
        description="The name of the document db.",
    )
    class_resource_collection_name: str = Field(
        ...,
        description="The name of the collection in the document db used for class resources.",
    )


class DocumentDB:
    """
    Define the document database.
    """
    def __init__(self, config: DocumentDBConfig) -> None:
        """Initialize document db."""
        self._client = MongoClient(
            username=config.username,
            password=config.password,
            host=config.fully_qualified_domain_name,
            port=config.port,
            tls=True,
            retryWrites=False,
        )
        db = self._client[config.database_name]
        self._class_resource_collection = db[config.class_resource_collection_name]

    def get_class_resources(self,
        ids: Union[list[UUID], UUID],
        from_class_ids: bool = False,
    ) -> list[ClassResourceDocument]:
        """Return the full class resources."""
        ids = [ids] if isinstance(ids, UUID) else ids
        ids = [str(id) for id in ids]
        db_filter: dict[str, Any]
        if from_class_ids:
            # this check ensures we find the root doc for the class resource and not a child doc.
            # Example: PDF vs pages in a PDF
            db_filter = {"class_id": {"$in": ids}}
            db_filter.update({"$or": [{"parent_resource_ids": {"$exists": False}}, {"parent_resource_ids": []}]})
            db_filter.update({"$and": [{"child_resource_ids": {"$exists": True}}, {"child_resource_ids": {"$ne": []}}]})
        else:
            db_filter = {"_id": {"$in": ids}}
        documents = list(self._class_resource_collection.find(db_filter))
        documents = [ClassResourceDocument.parse_obj(document) for document in documents]
        return documents
