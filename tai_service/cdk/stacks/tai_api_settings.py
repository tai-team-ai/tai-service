"""Define settings for instantiating the TAI API."""
import os
from ...api.runtime_settings import TaiApiSettings

TAI_API_SETTINGS = TaiApiSettings(
    secret_name=os.environ.get("DOC_DB_READ_WRITE_USER_PASSWORD_SECRET_NAME"),
    cluster_name="tai-service",
    db_name="class-resources",
)
