"""Define the indexer module."""
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from uuid import uuid4
import traceback
from loguru import logger
from pydantic import BaseModel, Field
from langchain.embeddings import OpenAIEmbeddings
from langchain import document_loaders
from langchain.document_loaders.base import BaseLoader
from langchain.text_splitter import TextSplitter
from langchain.schema import Document
from pinecone_text.sparse import SpladeEncoder
from pinecone_text.hybrid import hybrid_convex_scale


try:
    from taiservice.api.taibackend.indexer.data_ingestors import (
        InputDataIngestStrategy,
        InputDocument,
        S3ObjectIngestor,
        URLIngestor,
        IngestedDocument,
        SupportedInputFormat,
        get_splitter_text_splitter,
        get_page_number,
        get_total_page_count,
    )
    from taiservice.api.taibackend.databases.shared_schemas import ChunkMetadata
    from taiservice.api.taibackend.databases.pinecone_db import PineconeDBConfig, PineconeDB
    from taiservice.api.taibackend.databases.pinecone_db_schemas import PineconeDocuments, PineconeDocument
    from taiservice.api.taibackend.databases.document_db import DocumentDBConfig, DocumentDB
    from taiservice.api.taibackend.databases.document_db_schemas import ClassResourceChunkDocument
except ImportError:
    from taibackend.indexer.data_ingestors import (
        InputDataIngestStrategy,
        InputDocument,
        S3ObjectIngestor,
        URLIngestor,
        IngestedDocument,
        SupportedInputFormat,
        get_splitter_text_splitter,
        get_page_number,
        get_total_page_count,
    )
    from taibackend.databases.shared_schemas import ChunkMetadata
    from taibackend.databases.pinecone_db_schemas import PineconeDocuments, PineconeDocument
    from taibackend.databases.pinecone_db import PineconeDBConfig, PineconeDB
    from taibackend.databases.document_db import DocumentDBConfig, DocumentDB
    from taibackend.databases.document_db_schemas import ClassResourceChunkDocument


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

    def index_resource(self, document: InputDocument) -> None:
        """Index a document."""
        ingested_document = self._ingest_document(document)
        documents = self._load_and_split_document(ingested_document)

    def _load_and_split_document(self, document: IngestedDocument) -> list[Document]:
        """Split and load a document."""
        split_docs: list[Document] = []
        try:
            Loader: BaseLoader = getattr(document_loaders, document.input_format)
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
                    total_page_count=total_page_count,
                    **ingested_doc_metadata.dict(),
                ),
                **document.dict(),
            )
            chunk_documents.append(chunk_doc)
        vector_documents = self._embed_documents(chunk_documents)

    def _get_page_number(self, documents: Document, ingested_document: IngestedDocument) -> Optional[int]:
        """Get page number for document."""
        if ingested_document.input_format == SupportedInputFormat.PDF:
            return get_page_number(documents)

    def _embed_documents(self, documents: list[ClassResourceChunkDocument]) -> PineconeDocuments:
        """Embed documents."""
        texts = [document.page_content for document in documents]
        batches = [texts[i : i + self._batch_size] for i in range(0, len(texts), self._batch_size)]
        with ThreadPoolExecutor(max_workers=len(batches)) as executor:
            results = executor.map(self._embedding_strategy.em, batches)
            embeddings = [embedding for result in results for embedding in result]

    def _vector_document_from_dense_vector(self, dense_vectors: list[list[float]]) -> list[PineconeDocument]:
        """Get a vector document from a dense vector."""
        documents = []
        for dense_vector in dense_vectors:
            doc = PineconeDocument(
                id=uuid4(),
                
            )

    def _ingest_document(self, document: InputDocument) -> IngestedDocument:
        if document.input_data_ingest_strategy == InputDataIngestStrategy.S3_FILE_DOWNLOAD:
            ingestor = S3ObjectIngestor()
        elif document.input_data_ingest_strategy == InputDataIngestStrategy.URL_DOWNLOAD:
            ingestor = URLIngestor()
        else:
            raise NotImplementedError(f"Unsupported input data ingest strategy: {document.input_data_ingest_strategy}")
        return ingestor.ingest_data(document)
