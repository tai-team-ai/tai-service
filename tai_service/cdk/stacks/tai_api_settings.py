"""Define settings for instantiating the TAI API."""
import os
from ...api.runtime_settings import TaiApiSettings
from .search_databases_settings import DOCUMENT_DB_SETTINGS

TAI_API_SETTINGS = TaiApiSettings(
    secret_name=os.environ.get("DOC_DB_READ_WRITE_USER_PASSWORD_SECRET_NAME"),
    cluster_name=DOCUMENT_DB_SETTINGS.cluster_name,
    db_name=DOCUMENT_DB_SETTINGS.db_name,
)
