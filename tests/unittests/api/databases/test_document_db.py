"""Define tests for the document database."""


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
