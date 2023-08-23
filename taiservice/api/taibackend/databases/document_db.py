"""Define the pinecone database."""
from enum import Enum
from typing import Union
from uuid import UUID
from pydantic import BaseModel, Field
from pymongo import MongoClient
from ..shared_schemas import BasePydanticModel


class ClassResourceProcessingStatus(str, Enum):
    """Define the document status."""
    PENDING = "pending"
    PROCESSING = "processing"
    FAILED = "failed"
    DELETING = "deleting"
    COMPLETED = "completed"


class MinimumClassResourceDocument(BasePydanticModel):
    """Define the minimum class resource document."""
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
        ...,
        description="The status of the class resource.",
    )


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

    def create_new_class_resources(self, class_resources: Union[MinimumClassResourceDocument, list[MinimumClassResourceDocument]]) -> None:
        """Upsert the chunks of the class resource."""
        if isinstance(class_resources, MinimumClassResourceDocument):
            class_resources = [class_resources]
        for class_resource in class_resources:
            self._class_resource_collection.insert_one(class_resource.dict())
