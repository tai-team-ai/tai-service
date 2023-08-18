"""Define schemas for the user data database."""
from datetime import datetime, timezone
from uuid import uuid4
from pynamodb.models import Model
from pynamodb.attributes import (
    UnicodeAttribute,
    UTCDateTimeAttribute,
    NumberAttribute,
)
try:
    from ...runtime_settings import TaiApiSettings
except ImportError:
    from runtime_settings import TaiApiSettings


SETTINGS = TaiApiSettings()


class UserModel(Model):
    """Define a Tai Service user."""

    class Meta:
        """Define the configuration for the user model."""

        table_name = SETTINGS.user_table_name
        region = SETTINGS.aws_default_region.value
        host = SETTINGS.dynamodb_host

    id = UnicodeAttribute(hash_key=True, default_for_new=lambda: str(uuid4()), attr_name=SETTINGS.user_table_partition_key)
    last_access = UTCDateTimeAttribute(default_for_new=lambda: datetime.now(timezone.utc), attr_name=SETTINGS.user_table_sort_key)
    daily_token_count = NumberAttribute(default_for_new=0)
    token_count_last_reset = UTCDateTimeAttribute(default_for_new=lambda: datetime.now(timezone.utc))
