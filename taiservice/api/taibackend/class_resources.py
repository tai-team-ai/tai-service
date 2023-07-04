"""Define the class resources backend."""
from uuid import UUID
from loguru import logger
try:
    from taiservice.api.runtime_settings import TaiApiSettings
    from .databases.document_db_schemas import ClassResourceDocument, ClassResourceChunkDocument
    from .databases.document_db import DocumentDB, DocumentDBConfig
    from .databases.pinecone_db import PineconeDB, PineconeDBConfig
    from .indexer.indexer import (
        Indexer,
        InputDocument,
        IndexerConfig,
        InputDataIngestStrategy,
    )
except ImportError:
    from runtime_settings import TaiApiSettings
    from taibackend.databases.document_db_schemas import ClassResourceDocument, ClassResourceChunkDocument
    from taibackend.databases.document_db import DocumentDB, DocumentDBConfig
    from taibackend.databases.pinecone_db import PineconeDB, PineconeDBConfig
    from taibackend.indexer.indexer import (
        Indexer,
        InputDocument,
        IndexerConfig,
        InputDataIngestStrategy,
    )

class ClassResourcesBackend:
    """Class to handle the class resources backend."""
    def __init__(self, runtime_settings: TaiApiSettings) -> None:
        """Initialize the class resources backend."""
        self._pinecone_db_config = PineconeDBConfig.parse_obj(runtime_settings)
        self._pinecone_db = PineconeDB(self._pinecone_db_config)
        self._doc_db_config = DocumentDBConfig.parse_obj(runtime_settings)
        self._doc_db = DocumentDB(self._doc_db_config)
        self._indexer_config = IndexerConfig.parse_obj(runtime_settings)

    def get_class_resources(self, ids: list[UUID]) -> list[ClassResourceDocument]:
        """Get the class resources."""
        return self._doc_db.get_class_resources(ids)

    def _chunks_from_class_resource(self, class_resources: ClassResourceDocument) -> list[ClassResourceChunkDocument]:
        """Get the chunks from the class resources."""
        chunk_ids = class_resources.class_resource_chunk_ids
        return self._doc_db.get_class_resources(chunk_ids)

    def _delete_vectors_from_chunks(self, chunks: list[ClassResourceChunkDocument]) -> None:
        """Delete the vectors from the chunks."""
        vector_ids = [chunk.vector_id for chunk in chunks]
        self._pinecone_db.delete_vectors(vector_ids)

    def delete_class_resources(self, ids: list[UUID]) -> None:
        """Delete the class resources."""
        try:
            docs = self._doc_db.get_class_resources(ids)
            for doc in docs:
                if isinstance(doc, ClassResourceDocument) or isinstance(doc, ClassResourceChunkDocument):
                    if isinstance(doc, ClassResourceDocument):
                        chunk_docs = self._chunks_from_class_resource(doc)
                    chunk_docs = [doc]
                    self._delete_vectors_from_chunks(chunk_docs)
            self._doc_db.delete_class_resources(docs)
        except Exception as e:
            logger.critical(f"Failed to delete class resources: {e}")
            raise RuntimeError(f"Failed to delete class resources: {e}") from e

    def create_class_resources(
        self,
        class_resources: list[ClassResourceDocument],
        ingest_strategy: InputDataIngestStrategy
    ) -> None:
        """Create the class resources."""
        indexer = Indexer(self._indexer_config)
        for class_resource in class_resources:
            input_doc = InputDocument(
                input_data_ingest_strategy=ingest_strategy,
                **class_resource.dict()
            )
            indexer.index_resource(input_doc)
