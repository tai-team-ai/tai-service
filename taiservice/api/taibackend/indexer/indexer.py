"""Define the indexer module."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4
import traceback
from loguru import logger
from pydantic import BaseModel, Field
from langchain.embeddings import OpenAIEmbeddings
from langchain import document_loaders
from langchain.document_loaders.base import BaseLoader
from langchain.text_splitter import TextSplitter
from langchain.schema import Document
from pinecone_text.sparse import SpladeEncoder
try:
    from .data_ingestors import (
        get_splitter_text_splitter,
        get_page_number,
        get_total_page_count,
        S3ObjectIngestor,
        URLIngestor,
    )
    from .data_ingestor_schema import (
        IngestedDocument,
        InputFormat,
        InputDocument,
        InputDataIngestStrategy,
    )
    from ..shared_schemas import ChunkMetadata
    from ..databases.pinecone_db import PineconeDBConfig, PineconeDB
    from ..databases.pinecone_db_schemas import (
        PineconeDocuments,
        PineconeDocument,
        SparseVector,
    )
    from ..databases.document_db import DocumentDBConfig, DocumentDB
    from ..databases.document_db_schemas import (
        ClassResourceChunkDocument,
        ClassResourceDocument,
        ClassResourceProcessingStatus,
    )
except ImportError:
    from taibackend.indexer.data_ingestors import (
        get_splitter_text_splitter,
        get_page_number,
        get_total_page_count,
        S3ObjectIngestor,
        URLIngestor,
    )
    from taibackend.indexer.data_ingestor_schema import (
        IngestedDocument,
        InputFormat,
        InputDocument,
        InputDataIngestStrategy,
    )
    from taibackend.shared_schemas import ChunkMetadata
    from taibackend.databases.pinecone_db_schemas import (
        PineconeDocuments,
        PineconeDocument,
        SparseVector,
    )
    from taibackend.databases.pinecone_db import PineconeDBConfig, PineconeDB
    from taibackend.databases.document_db import DocumentDBConfig, DocumentDB
    from taibackend.databases.document_db_schemas import (
        ClassResourceChunkDocument,
        ClassResourceDocument,
        ClassResourceProcessingStatus,
    )


class OpenAIConfig(BaseModel):
    """Define the OpenAI config."""
    api_key: str = Field(
        ...,
        description="The API key of the OpenAI API.",
    )
    request_timeout: int = Field(
        ...,
        le=30,
        description="The timeout for requests to the OpenAI API.",
    )
    batch_size: int = Field(
        ...,
        ge=1,
        le=100,
        description="The batch size for requests to the OpenAI API.",
    )


class IndexerConfig(BaseModel):
    """Define the indexer config."""
    pinecone_db_config: PineconeDBConfig = Field(
        ...,
        description="The pinecone db config.",
    )
    document_db_config: DocumentDBConfig = Field(
        ...,
        description="The document db config.",
    )
    openai_config: OpenAIConfig = Field(
        ...,
        description="The OpenAI config.",
    )


class Indexer:
    """Define the indexer class."""
    def __init__(
        self,
        indexer_config: IndexerConfig,
    ) -> None:
        """Initialize indexer."""
        self._pinecone_db = PineconeDB(indexer_config.pinecone_db_config)
        self._document_db = DocumentDB(indexer_config.document_db_config)
        self._embedding_strategy = OpenAIEmbeddings(
            openai_api_key=indexer_config.openai_config.api_key,
            request_timeout=indexer_config.openai_config.request_timeout,
        )
        self._batch_size = indexer_config.openai_config.batch_size

    def index_resource(self, ingested_document: IngestedDocument) -> None:
        """Index a document."""
        try:
            class_resource_document = ClassResourceDocument(
                status=ClassResourceProcessingStatus.PROCESSING,
                **ingested_document.dict(),
            )
            chunk_documents = self._load_and_split_document(ingested_document)
            class_resource_document.class_resource_chunk_ids = [chunk_doc.id for chunk_doc in chunk_documents]
            vector_documents = self.embed_documents(chunk_documents, class_resource_document.class_id)
            self._load_class_resources_to_db(class_resource_document, chunk_documents)
            self._load_vectors_to_vector_store(vector_documents)
            class_resource_document.status = ClassResourceProcessingStatus.COMPLETED
            self._document_db.upsert_document(class_resource_document)
        except Exception as e:
            logger.error(traceback.format_exc())
            class_resource_document.status = ClassResourceProcessingStatus.FAILED
            self._document_db.upsert_document(class_resource_document)
            raise RuntimeError("Failed to index resource.") from e

    def _load_vectors_to_vector_store(self, vector_documents: PineconeDocuments) -> None:
        """Load vectors to vector store."""
        try:
            self._pinecone_db.upsert_vectors(
                documents=vector_documents,
            )
        except Exception as e:
            logger.critical(traceback.format_exc())
            raise RuntimeError("Failed to load vectors to vector store.") from e

    def _load_class_resources_to_db(self, document: ClassResourceDocument, chunk_documents: list[ClassResourceChunkDocument]) -> None:
        """Load the document to the db."""
        chunk_mapping = {
            chunk_doc.id: chunk_doc
            for chunk_doc in chunk_documents
        }
        try:
            failed_docs = self._document_db.upsert_class_resources(
                documents=[document],
                chunk_mapping=chunk_mapping
            )
        except Exception as e:
            logger.critical(traceback.format_exc())
            raise RuntimeError("Failed to load document to db.") from e
        if failed_docs:
            raise RuntimeError(f"{len(failed_docs)} documents failed to load to db: {failed_docs}")

    def _load_and_split_document(self, document: IngestedDocument) -> list[ClassResourceChunkDocument]:
        """Split and load a document."""
        split_docs: list[Document] = []
        try:
            Loader: BaseLoader = getattr(document_loaders, document.loading_strategy)
            try:
                # try to treat the pointer as a Path object and resolve it and convert to str
                document.data_pointer = str(Path(document.data_pointer).resolve())
            except Exception: # pylint: disable=broad-except
                logger.warning(f"Failed to resolve path: {document.data_pointer}")
            loader: BaseLoader = Loader(document.data_pointer)
            splitter: TextSplitter = get_splitter_text_splitter(document.input_format)
            split_docs = loader.load_and_split(splitter)
        except Exception as e: # pylint: disable=broad-except
            logger.critical(traceback.format_exc())
            raise RuntimeError("Failed to load and split document.") from e
        chunk_documents = []
        total_page_count = get_total_page_count(split_docs)
        ingested_doc_metadata = document.metadata
        ingested_doc_metadata.total_page_count = total_page_count
        for split_doc in split_docs:
            chunk_doc = ClassResourceChunkDocument(
                id=uuid4(),
                chunk=split_doc.page_content,
                vector_id=uuid4(),
                metadata=ChunkMetadata(
                    class_id=document.class_id,
                    page_number=get_page_number(split_doc),
                    **ingested_doc_metadata.dict(),
                ),
                **document.dict(exclude={"id", "metadata"}),
            )
            chunk_documents.append(chunk_doc)
        return chunk_documents

    def _get_page_number(self, documents: Document, ingested_document: IngestedDocument) -> Optional[int]:
        """Get page number for document."""
        if ingested_document.input_format == InputFormat.PDF:
            return get_page_number(documents)

    def embed_documents(self, documents: list[ClassResourceChunkDocument], class_id: UUID) -> PineconeDocuments:
        """Embed documents."""
        def _embed_batch(batch: list[ClassResourceChunkDocument]) -> list[PineconeDocument]:
            """Embed a batch of documents."""
            texts = [document.chunk for document in batch]
            dense_vectors = self._embedding_strategy.embed_documents(texts)
            vector_docs =  self.vector_document_from_dense_vectors(dense_vectors, batch)
            sparse_vectors = self.get_sparse_vectors(texts)
            for vector_doc, sparse_vector in zip(vector_docs, sparse_vectors):
                vector_doc.sparse_values = sparse_vector
            return vector_docs
        batches = [documents[i : i + self._batch_size] for i in range(0, len(documents), self._batch_size)]
        vector_docs = []
        with ThreadPoolExecutor(max_workers=len(batches)) as executor:
            results = executor.map(_embed_batch, batches)
            vector_docs = [vector_doc for result in results for vector_doc in result]
        return PineconeDocuments(class_id=class_id, documents=vector_docs)

    @staticmethod
    def get_sparse_vectors(texts: list[str]) -> list[SparseVector]:
        """Add sparse vectors to pinecone."""
        splade = SpladeEncoder()
        vectors = splade.encode_documents(texts)
        sparse_vectors = []
        for vec in vectors:
            sparse_vector = SparseVector.parse_obj(vec)
            sparse_vectors.append(sparse_vector)
        return sparse_vectors

    @staticmethod
    def vector_document_from_dense_vectors(
        dense_vectors: list[list[float]],
        documents: list[ClassResourceChunkDocument],
    ) -> list[PineconeDocument]:
        vector_docs = []
        for dense_vector, document in zip(dense_vectors, documents):
            doc = PineconeDocument(
                id=document.vector_id,
                metadata=ChunkMetadata.parse_obj(document.metadata),
                values=dense_vector,
            )
            vector_docs.append(doc)
        return vector_docs

    @staticmethod
    def ingest_document(document: InputDocument) -> IngestedDocument:
        """Ingest a document."""
        if document.input_data_ingest_strategy == InputDataIngestStrategy.S3_FILE_DOWNLOAD:
            ingestor = S3ObjectIngestor()
        elif document.input_data_ingest_strategy == InputDataIngestStrategy.URL_DOWNLOAD:
            ingestor = URLIngestor()
        else:
            raise NotImplementedError(f"Unsupported input data ingest strategy: {document.input_data_ingest_strategy}")
        return ingestor.ingest_data(document)
