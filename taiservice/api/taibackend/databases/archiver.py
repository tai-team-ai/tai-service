"""Define the utility for archiving data."""
from uuid import UUID
import boto3
from loguru import logger
# first imports are for local development, second imports are for deployment
try:
    from .archive_schemas import BaseArchiveRecord, StudentMessageRecord
    from ..taitutors.llm_schemas import (
        BaseMessage,
        StudentMessage,
    )
except ImportError:
    from taibackend.databases.archive_schemas import BaseArchiveRecord, StudentMessageRecord
    from taibackend.taitutors.llm_schemas import (
        BaseMessage,
        StudentMessage,
    )


class Archive:
    """Define the utility for archiving data."""
    def __init__(self, bucket_name: str) -> None:
        """Instantiate the utility for archiving data."""
        self._bucket_name = bucket_name
        self._bucket = boto3.resource('s3').Bucket(self._bucket_name)

    def archive_message(self, message: BaseMessage, class_id: UUID) -> None:
        """Store the message."""
        base_record = BaseArchiveRecord(
            class_id=class_id,
            timestamp=message.timestamp,
        )
        if isinstance(message, StudentMessage):
            archive_record = StudentMessageRecord(
                message=message.content,
                **base_record.dict(),
            )
        else:
            logger.warning(f"Archive does not support archiving messages of type {message.__class__.__name__}")
        self.put_archive_record(archive_record)

    def put_archive_record(self, archive_record: BaseArchiveRecord) -> None:
        """Put the archive record in the archive."""
        self._bucket.put_object(
            Key=archive_record.get_archive_object_key(),
            Body=archive_record.json(),
        )
