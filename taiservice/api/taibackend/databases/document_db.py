"""Define the pinecone database."""
from datetime import datetime
import traceback
from typing import Any, Callable, Optional, Union
from uuid import UUID
from pydantic import BaseModel, Field, ValidationError
from pymongo import MongoClient
from pymongo.collection import Collection
from loguru import logger
# first imports are for local development, second imports are for deployment
try:
    from .document_db_schemas import (
        BaseClassResourceDocument,
        ClassResourceDocument,
        ClassResourceChunkDocument,
    )
    from ..shared_schemas import UsageMetric
except ImportError:
    from taibackend.databases.document_db_schemas import (
        BaseClassResourceDocument,
        ClassResourceDocument,
        ClassResourceChunkDocument,
    )
    from taibackend.shared_schemas import UsageMetric

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
        self._client = MongoClient(
            username=config.username,
            password=config.password,
            host=config.fully_qualified_domain_name,
            port=config.port,
            tls=True,
            retryWrites=False,
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

    def find_one(self, doc_id: UUID, DocClass: BaseClassResourceDocument) -> Optional[BaseClassResourceDocument]:
        """Return the full class resource."""
        class_name = DocClass.__name__
        collection = self._document_type_to_collection[class_name]
        document = collection.find_one({"_id": str(doc_id)})
        if document is None:
            return None
        try:
            return DocClass.parse_obj(document)
        except ValidationError as e:
            logger.error(f"Failed to parse document: {document} for class: {class_name}")
            logger.error(traceback.format_exc())
            raise e

    def get_class_resources(self,
        ids: Union[list[UUID], UUID],
        DocClass: BaseClassResourceDocument,
        from_class_ids: bool=False,
        count_towards_metrics: bool=True,
    ) -> list[BaseClassResourceDocument]:
        """Return the full class resources."""
        ids = [ids] if isinstance(ids, UUID) else ids
        class_name = DocClass.__name__
        collection = self._document_type_to_collection[class_name]
        ids = [str(id) for id in ids]
        field_name = "class_id" if from_class_ids else "_id"
        documents = list(collection.find({field_name: {"$in": ids}}))
        documents = [DocClass.parse_obj(document) for document in documents]
        if count_towards_metrics:
            try:
                self._upsert_metrics_for_docs(documents, DocClass) # this let's us track usage DON'T REMOVE
            except Exception as e: # pylint: disable=broad-except
                logger.error(f"Failed to upsert metrics for documents: {e}")
                logger.error(traceback.format_exc())
        return documents

    def upsert_class_resources(
        self,
        documents: list[BaseClassResourceDocument],
        chunk_mapping: Optional[dict[UUID, ClassResourceChunkDocument]] = None, # pylint: disable=unused-argument
    ) -> list[BaseClassResourceDocument]:
        """Upsert the full class resources."""
        failed_documents = []
        def upsert_document(document: BaseClassResourceDocument) -> None:
            self.upsert_document(document)
            if isinstance(document, ClassResourceDocument):
                try:
                    chunks = [chunk_mapping[id] for id in document.class_resource_chunk_ids]
                except KeyError as e:
                    logger.error(f"Failed to find chunk: {e} for document: {document}")
                    raise e
                self.upsert_documents(chunks)
        for document in documents:
            self._execute_operation(upsert_document, document, failed_documents=failed_documents)
        return failed_documents

    def upsert_many_class_resources(self, documents: list[BaseClassResourceDocument]) -> list[BaseClassResourceDocument]:
        """Upsert the full class resources."""
        failed_documents = []
        def upsert_document(document: BaseClassResourceDocument) -> None:
            self.upsert_document(document)
        for document in documents:
            self._execute_operation(upsert_document, document, failed_documents=failed_documents)
        return failed_documents

    def delete_class_resources(self, documents: list[BaseClassResourceDocument]) -> list[BaseClassResourceDocument]:
        """Delete the full class resources."""
        failed_documents = []
        def delete_document(document: BaseClassResourceDocument) -> None:
            if isinstance(document, ClassResourceDocument):
                self._delete_documents(document.class_resource_chunk_ids)
            self._delete_document(document)
        for document in documents:
            self._execute_operation(delete_document, document, failed_documents=failed_documents)
        return failed_documents

    def upsert_documents(self, documents: list[BaseClassResourceDocument]) -> None:
        """Upsert the chunks of the class resource."""
        for document in documents:
            self.upsert_document(document)

    def upsert_document(self, document: BaseClassResourceDocument) -> None:
        """Upsert the chunks of the class resource."""
        collection = self._document_type_to_collection[document.__class__.__name__]
        collection.update_one(
            {"_id": document.id_as_str},
            {"$set": document.dict(serialize_dates=False, exclude={"id"})},
            upsert=True,
        )

    def run_aggregate_query(self, query: list[dict[str, Any]], DocClass: BaseClassResourceDocument) -> Any:
        """Run an aggregate query and return the results."""
        class_name = DocClass.__name__
        collection = self._document_type_to_collection[class_name]
        return collection.aggregate(query)

    def _upsert_metrics_for_docs(self, docs: list[BaseClassResourceDocument], DocClass: BaseClassResourceDocument) -> None:
        """Upsert the metrics of the class resource."""
        for doc in docs:
            collection = self._document_type_to_collection[DocClass.__name__]
            metric = UsageMetric(timestamp=datetime.utcnow())
            collection.find_one_and_update(
                {"_id": doc.id_as_str},
                {"$push": {"usage_log": metric.dict(serialize_dates=False)} }
            )
            doc.usage_log.append(metric) # updates the document in memory

    def _execute_operation(
        self,
        operation: Callable,
        document: BaseClassResourceDocument,
        *args: Any,
        failed_documents: Optional[list[BaseClassResourceDocument]] = None,
        **kwargs: Any
    ) -> bool:
        """Execute the operation and return the document if it fails."""
        try:
            operation(document, *args, **kwargs)
        except Exception as e: # pylint: disable=broad-except
            logger.error(f"Failed to execute operation: {e} on document: {document}")
            traceback.format_exc()
            failed_documents.append(document)

    def _delete_documents(self, docs: list[BaseClassResourceDocument]) -> None:
        """Delete the chunks of the class resource."""
        # sort by instance type
        for doc in docs:
            self._delete_document(doc)

    def _delete_document(self, doc: BaseClassResourceDocument) -> None:
        """Delete the chunks of the class resource."""
        collection = self._document_type_to_collection[doc.__class__.__name__]
        collection.delete_one({"_id": doc.id_as_str})
