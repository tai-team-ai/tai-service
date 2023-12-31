"""Define the pinecone database."""
from pathlib import Path
import traceback
from typing import Any, Callable, Optional, Union, Type
from uuid import UUID
from pydantic import BaseModel, Field, ValidationError
from pymongo import MongoClient
from pymongo.collection import Collection
from loguru import logger
from .document_db_schemas import (
    BaseClassResourceDocument,
    ClassResourceDocument,
    ClassResourceChunkDocument,
    StatefulClassResourceDocument,
)
from ..shared_schemas import UsageMetric


USAGE_LOG_FIELD_NAME = "usage_log"


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
    class_resource_chunk_collection_name: str = Field(
        ...,
        description="The name of the collection in the document db used for class resource chunks.",
    )


class DocumentDB:
    """
    Define the document database.

    In order to recover from failures, upsert and delete operations 
    follow a FIFO, where for upserts, the chunks are upserted before
    class resources, and for deletes, the chunks are deleted before
    class resources. This ensures that we still have pointers to the
    chunks in the class resources if failure occurs (allows us to retry)
    """
    def __init__(self, config: DocumentDBConfig) -> None:
        """Initialize document db."""
        if config.fully_qualified_domain_name == "localhost":
            tls=False
        else:
            tls=True
        kwargs = {}
        if "docdb.amazonaws.com" in config.fully_qualified_domain_name:
            kwargs = {
                "tlsCAFile": str((Path(__file__).parent / "global-bundle.pem").resolve()),
                "replicaSet": "rs0",
                "readPreference": "secondaryPreferred",
            }
        self._client = MongoClient(
            username=config.username,
            password=config.password,
            host=config.fully_qualified_domain_name,
            port=config.port,
            tls=tls,
            retryWrites=False,
            **kwargs,
        )
        self._doc_models = [
            ClassResourceChunkDocument,
            ClassResourceDocument,
        ]
        db = self._client[config.database_name]
        class_resource_collection = db[config.class_resource_collection_name]
        chunk_collection = db[config.class_resource_chunk_collection_name]
        self._document_type_to_collection = {
            ClassResourceDocument.__name__: class_resource_collection,
            ClassResourceChunkDocument.__name__: chunk_collection,
        }

    @property
    def supported_doc_models(self) -> list[BaseClassResourceDocument]:
        """Return the supported document models."""
        return self._doc_models

    def find_one(self, doc_id: UUID, DocClass: Type[BaseClassResourceDocument]) -> Optional[BaseClassResourceDocument]:
        """Return the full class resource."""
        collection = self._get_collection(DocClass)
        document = collection.find_one({"_id": str(doc_id)})
        if document is None:
            return None
        try:
            return DocClass.parse_obj(document)
        except ValidationError as e:
            logger.error(f"Failed to parse document: {document} for class: {DocClass.__name__}")
            logger.error(traceback.format_exc())
            raise e

    def get_class_resources(self,
        ids: Union[list[UUID], UUID],
        DocClass: Type[ClassResourceDocument | ClassResourceChunkDocument],
        from_class_ids: bool = False,
    ) -> list[ClassResourceDocument | ClassResourceChunkDocument]:
        """Return the full class resources."""
        ids = [ids] if isinstance(ids, UUID) else ids
        collection = self._get_collection(DocClass)
        ids = [str(id) for id in ids]
        db_filter: dict[str, Any]
        if from_class_ids:
            db_filter = {"class_id": {"$in": ids}}
            if DocClass == ClassResourceDocument:
                # this check ensures we find the root doc for the class resource and not a child doc.
                # Example: PDF vs pages in a PDF
                db_filter.update({"$or": [{"parent_resource_ids": {"$exists": False}}, {"parent_resource_ids": []}]})
                db_filter.update({"$and": [{"child_resource_ids": {"$exists": True}}, {"child_resource_ids": {"$ne": []}}]})
        else:
            db_filter = {"_id": {"$in": ids}}
        documents = list(collection.find(db_filter))
        documents = [DocClass.parse_obj(document) for document in documents]
        return documents

    def upsert_class_resources(
        self,
        documents: list[ClassResourceDocument],
        chunk_mapping: Optional[dict[UUID, ClassResourceChunkDocument]] = None, # pylint: disable=unused-argument
    ) -> None:
        """Upsert the full class resources."""
        self.upsert_documents(documents)
        if chunk_mapping:
            for document in documents:
                try:
                    chunks = [chunk_mapping[id] for id in document.class_resource_chunk_ids]
                except KeyError as e:
                    logger.error(f"Failed to find chunk: {e} for document: {document}")
                    raise e
                self.upsert_documents(chunks)

    def update_statuses(self, documents: list[ClassResourceDocument]) -> None:
        """Update the statuses of the class resources."""
        collection = self._get_collection(ClassResourceDocument)
        for document in documents:
            doc = collection.find_one_and_update(
                {"_id": str(document.id)},
                {"$set": {"status": document.status}},
            )
            if not doc:
                self.upsert_document(document)

    def delete_class_resources(self, documents: Union[list[BaseClassResourceDocument], BaseClassResourceDocument]) -> None:
        """Delete the full class resources."""
        if isinstance(documents, BaseClassResourceDocument):
            documents = [documents]
        for document in documents:
            if isinstance(document, ClassResourceDocument):
                self._delete_documents(document.class_resource_chunk_ids, ClassResourceChunkDocument)
            self._delete_document(document.id, document.__class__)

    def upsert_documents(self, documents: list[BaseClassResourceDocument]) -> None:
        """Upsert the chunks of the class resource."""
        for document in documents:
            self.upsert_document(document)

    def upsert_document(self, document: BaseClassResourceDocument) -> None:
        """Upsert the chunks of the class resource."""
        collection = self._get_collection(document.__class__)
        doc_dict = document.dict(serialize_dates=False, exclude={"id"})
        collection.update_one(
            {"_id": document.id_as_str},
            {"$set": doc_dict},
            upsert=True,
        )

    def run_aggregate_query(self, query: list[dict[str, Any]], DocClass: Type[BaseClassResourceDocument]) -> Any:
        """Run an aggregate query and return the results."""
        collection = self._get_collection(DocClass)
        return collection.aggregate(query)

    def _get_collection(self, DocClass: Type[BaseClassResourceDocument]) -> Collection:
        """Return the collection of the document."""
        if issubclass(DocClass, StatefulClassResourceDocument):
            return self._document_type_to_collection[ClassResourceDocument.__name__]
        elif issubclass(DocClass, ClassResourceChunkDocument):
            return self._document_type_to_collection[ClassResourceChunkDocument.__name__]
        else:
            raise ValueError(f"Invalid document type: {DocClass}")

    def upsert_metric(self, doc_id: UUID, metric: UsageMetric, DocClass: Union[Type[ClassResourceDocument], Type[ClassResourceChunkDocument]]) -> None:
        """Upsert the metrics of the class resource."""
        collection = self._get_collection(DocClass)
        collection.find_one_and_update(
            {"_id": str(doc_id)},
            {"$push": {USAGE_LOG_FIELD_NAME: metric.dict(serialize_dates=False)}},
        )

    def _delete_documents(self, ids: list[UUID], DocClass: Type[BaseClassResourceDocument]) -> None:
        """Delete the chunks of the class resource."""
        collection = self._get_collection(DocClass)
        collection.delete_many({"_id": {"$in": [str(id) for id in ids]}})

    def _delete_document(self, doc_id: UUID, DocClass: Type[BaseClassResourceDocument]) -> None:
        """Delete the chunks of the class resource."""
        collection = self._get_collection(DocClass)
        collection.delete_one({"_id": str(doc_id)})
