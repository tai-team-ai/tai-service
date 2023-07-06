"""Define tests for the document database."""
from unittest.mock import patch
from taiservice.api.taibackend.databases.document_db import DocumentDB, DocumentDBConfig
from taiservice.api.taibackend.databases.document_db_schemas import BaseClassResourceDocument
from tests.unit.api.databases.test_shared_schemas import (
    assert_schema1_inherits_from_schema2,
)

def test_model_inheritance_order():
    """Ensure that the model inheritance order is correct."""
    with patch('taiservice.api.taibackend.databases.document_db.MongoClient'):
        config = DocumentDBConfig(
            username="username",
            password="password",
            fully_qualified_domain_name="fully_qualified_domain_name",
            port=1234,
            database_name="database_name",
            class_resource_chunk_collection_name="class_resource_chunk_collection_name",
            class_resource_collection_name="class_resource_collection_name",
        )
        document_db = DocumentDB(config)
        models = document_db.supported_doc_models
        for model in models:
            assert_schema1_inherits_from_schema2(model, BaseClassResourceDocument)

# future test case for upsert
# class_id = uuid4()
# chunk_id = uuid4()
# chunk_mapping = {
#     chunk_id: ClassResourceChunkDocument(
#         id=chunk_id,
#         chunk="this is a chunk",
#         class_id=class_id,
#         full_resource_url="https://example.com/resource",
#         metadata=ChunkMetadata(
#             description="description",
#             resource_type=ClassResourceType.PDF,
#             tags=["tag1", "tag2"],
#             title="title",
#             total_page_count=1,
#             page_number=1,
#             class_id=class_id,
#         ),
#         vector_id=uuid4(),
#     )
# }
# class_resource = ClassResourceDocument(
#     class_id=class_id,
#     class_resource_chunk_ids=[id for id in chunk_mapping],
#     full_resource_url="https://example.com/resource",
#     id=uuid4(),
#     metadata=Metadata(
#         description="description",
#         resource_type=ClassResourceType.PDF,
#         tags=["tag1", "tag2"],
#         title="title",
#         total_page_count=1,
#     ),
#     status=ClassResourceProcessingStatus.COMPLETED,
# )
# document_db.upsert_class_resources(
#     documents=[class_resource],
#     chunk_mapping=chunk_mapping,
# )
