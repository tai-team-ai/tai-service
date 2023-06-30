from pydantic import Field

# first imports are for local development, second imports are for deployment
try:
    from taiservice.cdk.constructs.customresources.document_db.settings import (
        BaseDocumentDBSettings,
        BuiltInMongoDBRoles,
        MongoDBUser,
    )
except ImportError:
    # this module must be copied to the root of the lambda for deployment
    from settings import BaseDocumentDBSettings, BuiltInMongoDBRoles, MongoDBUser


SETTINGS_STATE_ATTRIBUTE_NAME = "runtime_settings"

class TaiApiSettings(BaseDocumentDBSettings, MongoDBUser):
    """Define the configuration model for the TAI API service."""

    role: BuiltInMongoDBRoles = Field(
        default=BuiltInMongoDBRoles.READ_WRITE,
        const=True,
        description="The role for the TAI API service when connecting to the DocumentDB.",
    )
