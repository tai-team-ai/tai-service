from ..constructs.customresources.document_db.document_db_custom_resource import (
    BaseDocumentDBSettings,
    MongoDBUser,
    BuiltInMongoDBRoles,
)

class TaiApiSettings(BaseDocumentDBSettings, MongoDBUser):
    """Define the configuration model for the TAI API service."""

    role: BuiltInMongoDBRoles = Field(
        default=BuiltInMongoDBRoles.READ_WRITE,
        const=True,
        description="The role for the TAI API service when connecting to the DocumentDB.",
    )