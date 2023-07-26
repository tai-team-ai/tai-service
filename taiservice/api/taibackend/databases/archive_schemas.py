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
        return f"{class_id}/{archive_record_type}/{timestamp}.json"


class StudentMessageRecord(BasePydanticModel):
    """Define the student message record for archiving student messages"""
    message: str = Field(
        ...,
        description="The message of the student.",
    )

    def get_archive_object_key(self) -> str:
        """Return the object key of the student message record."""
        return f"{self.class_id}/{self.__class__.__name__}/{self.date.strftime('%Y-%m-%d-%H-%M-%S-%f')}.json"
