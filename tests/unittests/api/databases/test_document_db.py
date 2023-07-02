"""Define tests for the document database."""
from unittest.mock import patch
from taiservice.api.taibackend.databases.document_db import DocumentDB, DocumentDBConfig
from tests.unittests.api.databases.test_shared_schemas import (
    assert_schema2_inherits_from_schema1,
)


def test_model_inheritance_order():
    with patch('taiservice.api.taibackend.databases.document_db.MongoClient') as mock_client:
        config = DocumentDBConfig(
            username="username",
            password="password",
            fully_qualified_domain_name="fully_qualified_domain_name",
            port=1234,
            database_name="database_name",
            collection_name="collection_name",
        )
        document_db = DocumentDB(config)

        # Access the supported_doc_models property
        models = document_db.supported_doc_models

        # Continue with the rest of your assertions and tests
        for i in range(len(models) - 1):
            assert_schema2_inherits_from_schema1(
                models[i + 1],
                models[i],
            )
