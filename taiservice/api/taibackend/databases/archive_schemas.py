"""Define schemas for logging and archiving data."""
from uuid import UUID
from datetime import datetime
from pydantic import Field

# first imports are for local development, second imports are for deployment
try:
    from ..shared_schemas import BasePydanticModel
except ImportError:
    from taibackend.shared_schemas import BasePydanticModel


class BaseArchiveRecord(BasePydanticModel):
    """Define the base archive record."""

    class_id: UUID = Field(
        ...,
        description="The ID of the class that the archived object belongs to.",
    )
    timestamp: datetime = Field(
        ...,
        description="The date of the archived object.",
    )

    def get_archive_object_key(self) -> str:
        """Return the object key of the archive record."""
        class_id = f"class_id={self.class_id}"
        archive_record_type = f"archive_record_type={self.__class__.__name__}"
        timestamp = f"timestamp={self.timestamp.strftime('%Y-%m-%d-%H-%M-%S-%f')}"
        return f"{class_id}/{archive_record_type}/{timestamp}/record.json"

    @classmethod
    def get_archive_prefix(cls, class_id: UUID) -> str:
        """Return the prefix of the archive record."""
        class_id_param: str = f"class_id={class_id}"
        archive_record_type = f"archive_record_type={cls.__name__}"
        return f"{class_id_param}/{archive_record_type}"


class HumanMessageRecord(BaseArchiveRecord):
    """Define the student message record for archiving student messages"""

    message: str = Field(
        ...,
        description="The message of the student.",
    )
