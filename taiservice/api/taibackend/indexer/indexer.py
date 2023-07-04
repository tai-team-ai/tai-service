"""Define the indexer module."""
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, validator
from langchain.embeddings import OpenAIEmbeddings
from langchain.schema import Document

try:
    from taiservice.api.taibackend.indexer.data_ingestors import (
        InputDataIngestStrategy,
        InputDocument,
        Ingestor,
        S3ObjectIngestor,
        URLIngestor,
    )
    from taiservice.api.taibackend.databases.pinecone_db import PineconeDBConfig, PineconeDB
    from taiservice.api.taibackend.databases.document_db import DocumentDBConfig, DocumentDB
except ImportError:
    from taibackend.indexer.data_ingestors import (
        InputDataIngestStrategy,
        InputDocument,
        Ingestor,
        S3ObjectIngestor,
        URLIngestor,
    )
    from taibackend.databases.pinecone_db import PineconeDBConfig, PineconeDB
    from taibackend.databases.document_db import DocumentDBConfig, DocumentDB


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

    def index_resource(self, document: InputDocument) -> None:
        """Index a document."""


    def _ingest_document(self, document: InputDocument) -> None:
        """Ingest a document."""
        if document.input_data_ingest_strategy == InputDataIngestStrategy.S3_FILE_DOWNLOAD:
            

