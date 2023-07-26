"""Define metrics utilities and classes for retrieving and aggregating metrics for the TAIService API."""

from datetime import date, timedelta
from typing import Optional
from uuid import UUID
from pydantic import Field, conint
# first imports are for local development, second imports are for deployment
try:
    from .shared_schemas import BaseOpenAIConfig, BasePydanticModel, DateRange
    from .databases.document_db_schemas import ClassResourceChunkDocument
    from .databases.archiver import Archive
    from .databases.archive_schemas import StudentMessageRecord
    from .databases.document_db import DocumentDB
    from .databases.pinecone_db import PineconeDB
    from .taitutors.llm import TaiLLM
except ImportError:
    from shared_schemas import BaseOpenAIConfig, BasePydanticModel, DateRange
    from databases.document_db_schemas import ClassResourceChunkDocument
    from databases.archiver import Archive
    from databases.archive_schemas import StudentMessageRecord
    from databases.document_db import DocumentDB
    from databases.pinecone_db import PineconeDB
    from taitutors.llm import TaiLLM


class MetricsConfig(BasePydanticModel):
    """Define the metrics config."""
    document_db_instance: DocumentDB = Field(
        ...,
        description="The instance of the document db.",
    )
    pinecone_db_instance: PineconeDB = Field(
        ...,
        description="The instance of the pinecone db.",
    )
    archive: Archive = Field(
        ...,
        description="The instance of the archive.",
    )
    openai_config: BaseOpenAIConfig = Field(
        ...,
        description="The config for the OpenAI API.",
    )

    class Config:
        """Define the config for the metrics config."""
        arbitrary_types_allowed = True


class BaseFrequentlyAccessedObjects(BasePydanticModel):
    """Define a base schema for common resources."""
    class_id: UUID = Field(
        ...,
        description="The ID that the common resource belongs to.",
    )
    date_range: DateRange = Field(
        default_factory=DateRange,
        description="The date range over which the appearances of the common resource are counted.",
    )


class BaseFrequentlyAccessedObject(BasePydanticModel):
    """Define a base schema for ranked common resources."""
    rank: conint(ge=1) = Field(
        ...,
        description="The rank of the object when ranked by appearances during the date range.",
    )
    appearances_during_period: conint(ge=1) = Field(
        ...,
        description="The number of times the object appeared during the date range.",
    )


class CommonQuestion(BaseFrequentlyAccessedObject):
    """Define a schema for a common question."""
    question: str = Field(
        ...,
        description="The question that was most common during the date range.",
    )


class FrequentlyAccessedResource(BaseFrequentlyAccessedObject):
    """Define a schema for a common resource."""
    resource: ClassResourceChunkDocument = Field(
        ...,
        description="The resource that was most common during the date range.",
    )


class CommonQuestions(BaseFrequentlyAccessedObjects):
    """Define a schema for common questions."""
    common_questions: list[CommonQuestion] = Field(
        ...,
        description="The list of the most frequently asked questions during the date range.",
    )


class FrequentlyAccessedResources(BaseFrequentlyAccessedObjects):
    """Define a schema for common resources."""
    resources: list[FrequentlyAccessedResource] = Field(
        ...,
        description="The list of the most frequently accessed resources during the date range.",
    )


class Metrics:
    """Define the metrics class."""
    def __init__(self, config: MetricsConfig):
        """Initialize the metrics class."""
        self._document_db = config.document_db_instance
        self._pinecone_db = config.pinecone_db_instance
        self._openai_config = config.openai_config
        self._archive = config.archive

    def _get_student_messages(self, class_id: UUID, date_range: Optional[DateRange] = None) -> list[str]:
        """Get student records."""
        if date_range is None:
            date_range = DateRange()
        records = self._archive.get_archived_messages(
            class_id=class_id,
            date_range=date_range,
            RecordClass=StudentMessageRecord,
        )
        assert all(isinstance(rec, StudentMessageRecord) for rec in records)
        rec: StudentMessageRecord
        messages = []
        for rec in records:
            messages.append(rec.message)
        return messages

    def _rank_summaries(self, summary: list[str]) -> list[CommonQuestion]:
        """Rank messages."""
        ranked_messages = []
        for message in summary:
            msg = CommonQuestion(
                rank=1,
                appearances_during_period=1,
                question=message,
            )
            ranked_messages.append(msg)
        return ranked_messages

    def get_most_frequently_asked_questions(self, class_id: UUID, date_range: Optional[DateRange] = None) -> CommonQuestions:
        """Get the most frequently asked questions."""
        if date_range is None:
            date_range = DateRange()
        messages = self._get_student_messages(class_id, date_range)
        llm = TaiLLM(self._openai_config)
        messages = llm.summarize_student_messages(messages, as_questions=True)
        common_questions = CommonQuestions(
            class_id=class_id,
            date_range=date_range,
            common_questions=self._rank_summaries(messages)
        )
        return common_questions


    def get_most_frequently_accessed_resources(self, class_id: UUID, date_range: Optional[DateRange] = None) -> FrequentlyAccessedResources:
        """Get the most frequently accessed resources."""
        if date_range is None:
            date_range = DateRange()
        pipeline_usage = [
            {
                '$match': {
                    'class_id': str(class_id),
                }
            },
            {
                '$unwind': '$usage_log'
            },
            {
                '$match': {
                    'usage_log.timestamp': {'$gte': date_range.start_date, '$lte': date_range.end_date} ,
                },
            },
            {
                '$group': {
                    '_id': '$_id',
                    'resource_count': {'$sum': 1 },
                }
            },
            {
                '$sort': {'resource_count': -1}
            }
        ]
        resources_usage = list(self._document_db.run_aggregate_query(pipeline_usage, ClassResourceChunkDocument))
        ids = [resource_usage['_id'] for resource_usage in resources_usage] 
        frequently_accessed_resources: list[FrequentlyAccessedResource] = []
        for rank, doc_id in enumerate(ids, 1):
            document = self._document_db.find_one(doc_id, ClassResourceChunkDocument)
            frequently_accessed_resources.append(FrequentlyAccessedResource(
                rank=rank,
                appearances_during_period=resources_usage[rank - 1]['resource_count'],
                resource=document,
            ))
        frequently_accessed_resources = FrequentlyAccessedResources(
            class_id=class_id,
            date_range=DateRange(
                start_date=date_range.start_date,
                end_date=date_range.end_date,
            ),
            resources=[resource.dict() for resource in frequently_accessed_resources]
        )
        return frequently_accessed_resources
