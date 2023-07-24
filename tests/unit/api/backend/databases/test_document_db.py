"""Define tests for the document database."""
from unittest.mock import MagicMock, patch
from uuid import uuid4
from pydantic import BaseModel
from taiservice.api.taibackend.databases.document_db import DocumentDB, DocumentDBConfig
from taiservice.api.taibackend.databases.document_db_schemas import ClassResourceDocument, BaseClassResourceDocument
from tests.unit.api.backend.databases.test_shared_schemas import (
    assert_schema1_inherits_from_schema2,
)


def get_db_config() -> DocumentDBConfig:
    """Get a DocumentDBConfig object."""
    return DocumentDBConfig(
        username="username",
        password="password",
        fully_qualified_domain_name="fully_qualified_domain_name",
        port=1234,
        database_name="database_name",
        class_resource_chunk_collection_name="class_resource_chunk_collection_name",
        class_resource_collection_name="class_resource_collection_name",
    )


class DummyDoc(BaseModel):
    """Define a dummy document."""
    dummy_field: str


def test_model_inheritance_order():
    """Ensure that the model inheritance order is correct."""
    with patch('taiservice.api.taibackend.databases.document_db.MongoClient'):
        config = get_db_config()
        document_db = DocumentDB(config)
        models = document_db.supported_doc_models
        for model in models:
            assert_schema1_inherits_from_schema2(model, BaseClassResourceDocument)

def test_get_class_resources_calls_upsert_metrics_for_docs_and_matching_length_documents():
    """Test get_class_resources method calls upsert_metrics_for_docs and has matching length of documents."""
    with patch('taiservice.api.taibackend.databases.document_db.MongoClient'):
        config = get_db_config()
        document_db = DocumentDB(config)

        # Create a MagicMock for the collection object and configure the find method to return a list of documents
        collection_mock = MagicMock()
        collection_mock.find.return_value = [DummyDoc(dummy_field="dummy_field").dict() for _ in range(2)]

        # Configure the DocumentDB's _document_type_to_collection attribute to return the MagicMock collection
        document_db._document_type_to_collection = {
            DummyDoc.__name__: collection_mock,
        }

        # Patch the _upsert_metrics_for_docs method in the DocumentDB instance
        with patch.object(document_db, '_upsert_metrics_for_docs', autospec=True) as mock_upsert_metrics:

            # Call the get_class_resources method with a list of UUIDs
            ids = [uuid4(), uuid4()]
            documents = document_db.get_class_resources(ids, DummyDoc)

            # Assert that the _upsert_metrics_for_docs method is called once
            mock_upsert_metrics.assert_called_once()

            # Assert that the length of the returned documents matches the length of the input ids
            assert len(documents) == len(ids)
