from pydantic import Field

# first imports are for local development, second imports are for deployment
try:
    from tai_service.cdk.constructs.customresources.document_db.settings import (
        BaseDocumentDBSettings,
        BuiltInMongoDBRoles,
        MongoDBUser,
    )
except ImportError:
    from settings import BaseDocumentDBSettings, BuiltInMongoDBRoles, MongoDBUser


SETTINGS_STATE_ATTRIBUTE_NAME = "runtime_settings"

class TaiApiSettings(MongoDBUser, BaseDocumentDBSettings):
    """Define the configuration model for the TAI API service."""

    role: BuiltInMongoDBRoles = Field(
        default=BuiltInMongoDBRoles.READ_WRITE,
        const=True,
        description="The role for the TAI API service when connecting to the DocumentDB.",
    )
