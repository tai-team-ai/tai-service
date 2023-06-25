"""Define settings for instantiating search databases."""
import os
from dotenv import load_dotenv
from tai_service.cdk.constructs.customresources.document_db.document_db_custom_resource import (
    DocumentDBSettings,
    CollectionConfig,
    MongoDBUser,
    BuiltInMongoDBRoles,
)
from tai_service.cdk.constructs.customresources.pinecone_db.pinecone_db_custom_resource import (
    PodType,
    PodSize,
    DistanceMetric,
    PineconeIndexConfig,
    PineconeDBSettings,
)

INDEXES = [
    PineconeIndexConfig(
        name="tai-index",
        dimension=768,
        metric=DistanceMetric.DOT_PRODUCT,
        pod_instance_type=PodType.S1,
        pod_size=PodSize.X1,
        pods=1,
        replicas=1,
    )
]
PINECONE_DB_SETTINGS = PineconeDBSettings(indexes=INDEXES)

COLLECTION_CONFIG = [
    CollectionConfig(
        name="class-resource",
        fields_to_index=["class_id", "resource_id"],
    ),
    CollectionConfig(
        name="class-resource-chunk",
        fields_to_index=["class_id", "resource_id", "chunk_id"],
    ),
]

load_dotenv()
USER_CONFIG = [
    MongoDBUser(
        username="readOnlyUser",
        role=BuiltInMongoDBRoles.READ,
        password_secret_name=os.environ.get("DOC_DB_READ_ONLY_USER_PASSWORD_SECRET_NAME"),
    ),
    MongoDBUser(
        username="readWriteUser",
        role=BuiltInMongoDBRoles.READ_WRITE,
        password_secret_name=os.environ.get("DOC_DB_READ_WRITE_USER_PASSWORD_SECRET_NAME"),
    ),
]
DOCUMENT_DB_SETTINGS = DocumentDBSettings(
    admin_username="adminUser",
    cluster_name="tai-service",
    collection_config=COLLECTION_CONFIG,
    db_name="class-resources",
    user_config=USER_CONFIG,
)