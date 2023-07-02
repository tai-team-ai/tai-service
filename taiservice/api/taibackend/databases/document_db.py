"""Define the pinecone database."""
from uuid import UUID
from pydantic import BaseModel, Field
from pymongo import MongoClient
# first imports are for local development, second imports are for deployment
try:
    from .document_db_schemas import BaseClassResourceDocument
except ImportError:
    from taibackend.databases.document_db_schemas import BaseClassResourceDocument

class DocumentDB(BaseModel):
    """Define the document database."""

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
    collection_name: str = Field(
        ...,
        description="The name of the collection in the document db.",
    )

    def __init__(self) -> None:
        """Initialize document db."""
        self._client = MongoClient(
            host=self.fully_qualified_domain_name,
            port=self.port,
            username=self.username,
            password=self.password,
            tls=True,
            retryWrites=False,
        )
        self._collection = self._client[self.database_name][self.collection_name]

    def get_class_resources(self, ids: list[UUID]) -> list[BaseClassResourceDocument]:
        """Return the full class resources."""
        documents = self._collection.find({"_id": {"$in": ids}})
        return [BaseClassResourceDocument.parse_obj(document) for document in documents]

    def upsert_class_resources(self, documents: list[BaseClassResourceDocument]) -> None:
        """Upsert the full class resources."""
        for document in documents:
            self._collection.update_one(
                {"_id": document.id},
                {"$set": document.dict()},
                upsert=True,
            )