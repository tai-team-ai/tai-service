"""Define the pinecone database."""
from enum import Enum
from multiprocessing.pool import ApplyResult
from typing import List
from uuid import UUID
from pydantic import BaseModel, Field
import pinecone
# first imports are for local development, second imports are for deployment
try:
    from .pinecone_db_schemas import PineconeDocuments, PineconeDocument
except ImportError:
    from taibackend.databases.pinecone_db_schemas import PineconeDocuments, PineconeDocument

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
        docs = [doc.dict() for doc in documents.documents]
        return docs

    def _get_exported_batches(self, documents: PineconeDocuments) -> List[PineconeDocuments]:
        batches = []
        documents = self._export_documents(documents)
        for i in range(0, len(documents), self._max_vectors_per_operation):
            batches.append(documents[i : i + self._max_vectors_per_operation])
        return batches

    def _execute_async_pinecone_operation(self, index_operation_name: str, documents: PineconeDocuments) -> None:
        batches = self._get_exported_batches(documents)
        with pinecone.Index(self._index_name, pool_threads=self._number_threads) as index:
            async_results = []
            operation = getattr(index, index_operation_name)
            for batch in batches:
                async_results.append(operation(batch, async_req=True, namespace=str(documents.class_id)))
            async_result: ApplyResult
            for async_result in async_results:
                async_result.get()

    def upsert_vectors(self, documents: PineconeDocuments) -> None:
        """Upsert vectors into pinecone db."""
        self._execute_async_pinecone_operation("upsert", documents)

    def get_similar_vectors(self, document: PineconeDocument) -> PineconeDocuments:
        """Get similar vectors from pinecone db."""
        results = self.index.query(
            namespace=PineconeDocument.metadata.class_id,
            include_values=True,
            include_metadata=True,
            vector=document.values,
            sparse_vector=document.sparse_values,
            top_k=4,
        )
        return PineconeDocuments.parse_obj(**results.to_dict())

    def delete_vectors(self, documents: PineconeDocuments) -> None:
        """Delete vectors from pinecone db."""
        self._execute_casync_pinecone_operation("delete", documents)

    def delete_all_vectors(self, class_id: UUID) -> None:
        """Delete all vectors from pinecone db."""
        self.index.delete(namespace=str(class_id), delete_all=True)
