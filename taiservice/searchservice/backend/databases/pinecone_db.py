"""Define the pinecone database."""
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass
from multiprocessing.pool import ApplyResult
from enum import Enum
import os
from typing import List
from uuid import UUID
from loguru import logger
from pydantic import BaseModel, Field
import pinecone
from pinecone_text.hybrid import hybrid_convex_scale
from .pinecone_db_schemas import PineconeDocuments, PineconeDocument


class Environment(str, Enum):
    """Define the environment of the pinecone db."""

    US_EAST_1_AWS = "us-east-1-aws"


class PineconeDBConfig(BaseModel):
    """Define the pinecone database config."""

    api_key: str = Field(
        ...,
        description="The api key of the pinecone db.",
    )
    environment: Environment = Field(
        ...,
        description="The environment of the pinecone db.",
    )
    index_name: str = Field(
        ...,
        description="The name of the pinecone index.",
    )

@dataclass
class PineconeQueryFilter:
    """Define the pinecone query filter."""
    alpha: float = 0.8
    filter_by_chapters: bool = False
    filter_by_sections: bool = False
    filter_by_resource_type: bool = False


class PineconeDB:
    """Define the pinecone database."""

    def __init__(self, config: PineconeDBConfig) -> None:
        """Initialize pinecone db."""
        pinecone.init(api_key=config.api_key, environment=config.environment)
        self._index_name = config.index_name
        self._number_threads = 50
        self._max_vectors_per_operation = 100

    @property
    def index(self) -> pinecone.Index:
        """Return the pinecone index."""
        return pinecone.Index(self._index_name)

    def _export_documents(self, documents: PineconeDocuments) -> List[dict]:
        docs = [doc.dict(exclude={'score'}, exclude_none=True) for doc in documents.documents]
        return docs

    def _get_exported_batches(self, documents: PineconeDocuments) -> List[PineconeDocuments]:
        batches = []
        documents = self._export_documents(documents)
        for i in range(0, len(documents), self._max_vectors_per_operation):
            batches.append(documents[i : i + self._max_vectors_per_operation])
        return batches

    def _execute_async_pinecone_operation(self, index_operation_name: str, documents: PineconeDocuments) -> None:
        batches = self._get_exported_batches(documents)
        if not os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
            with pinecone.Index(self._index_name, pool_threads=self._number_threads) as index:
                async_results = []
                operation = getattr(index, index_operation_name)
                for batch in batches:
                    async_results.append(operation(batch, async_req=True, namespace=str(documents.class_id)))
                async_result: ApplyResult
                for async_result in async_results:
                    async_result.get()
        else:
            for batch in batches:
                operation = getattr(self.index, index_operation_name)
                operation(batch, namespace=str(documents.class_id))

    def upsert_vectors(self, documents: PineconeDocuments) -> None:
        """Upsert vectors into pinecone db."""
        self._execute_async_pinecone_operation("upsert", documents)

    def get_similar_documents(
        self,
        document: PineconeDocument,
        doc_to_return: int = 4,
        filter: PineconeQueryFilter = PineconeQueryFilter(),
    ) -> PineconeDocuments:
        """
        Get similar vectors from pinecone db.

        The chapter and section filters will be ORed together while
        the resource type filter will be ANDed with the other filters.

        Args:
            document: The document to get similar vectors for.
            alpha: The alpha value for the hybrid convex scale  
            between 0 and 1 where 0 == sparse only and 1 == dense only
            doc_to_return: The number of documents to return
            filter_by_chapter: Whether to filter by chapter
            filter_by_section: Whether to filter by section
            filter_by_resource_type: Whether to filter by resource type
        """
        if document.sparse_values:
            assert 0 <= filter.alpha <= 1, "alpha must be between 0 and 1"
            dense, sparse = hybrid_convex_scale(document.values, document.sparse_values.dict(), filter.alpha)
        else:
            dense = document.values
            sparse = None
        and_filter: list[dict] = []
        or_filter: list[dict] = []
        if filter.filter_by_chapters:
            or_filter.append({"chapters": {"$in": document.metadata.chapters}})
        if filter.filter_by_sections:
            or_filter.append({"sections": {"$in": document.metadata.sections}})
        if filter.filter_by_resource_type:
            and_filter.append({"resource_type": document.metadata.resource_type})
        if or_filter:
            and_filter.append({"$or": or_filter})
        meta_data_filter = {"$and": and_filter} if and_filter else {}
        results = self.index.query(
            namespace=str(document.metadata.class_id),
            include_values=True,
            include_metadata=True,
            vector=dense,
            sparse_vector=sparse,
            top_k=doc_to_return,
            filter=meta_data_filter,
        )
        docs = PineconeDocuments(class_id=document.metadata.class_id, documents=[])
        matches = results.to_dict()['matches']
        logger.info(f"Found {len(matches)} matches")
        for result in matches:
            doc = PineconeDocument(**result)
            logger.info(f"Score: {doc.score}")
            docs.documents.append(doc)
        # sort the documents by score
        docs.documents.sort(key=lambda doc: doc.score, reverse=True)
        return docs

    def delete_vectors(self, documents: PineconeDocuments) -> None:
        """Delete vectors from pinecone db."""
        self._execute_async_pinecone_operation("delete", documents)

    def delete_all_vectors(self, class_id: UUID) -> None:
        """Delete all vectors from pinecone db."""
        self.index.delete(namespace=str(class_id), delete_all=True)
