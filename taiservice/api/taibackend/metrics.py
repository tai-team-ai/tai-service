"""Define metrics utilities and classes for retrieving and aggregating metrics for the TAIService API."""
from typing import Optional
from uuid import UUID
from pydantic import Field, conint
# first imports are for local development, second imports are for deployment
try:
    from ...api.taibackend.shared_schemas import BasePydanticModel, DateRange
    from ...api.taibackend.databases.archiver import Archive
    from ...api.taibackend.databases.archive_schemas import HumanMessageRecord
    from ...api.taibackend.taitutors.llm import TaiLLM, ChatOpenAIConfig
except ImportError:
    from shared_schemas import BasePydanticModel, DateRange
    from databases.archiver import Archive
    from databases.archive_schemas import HumanMessageRecord
    from taitutors.llm import TaiLLM, ChatOpenAIConfig


class MetricsConfig(BasePydanticModel):
    """Define the metrics config."""
    archive: Archive = Field(
        ...,
        description="The instance of the archive.",
    )
    openai_config: ChatOpenAIConfig = Field(
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


class CommonQuestions(BaseFrequentlyAccessedObjects):
    """Define a schema for common questions."""
    common_questions: list[CommonQuestion] = Field(
        ...,
        description="The list of the most frequently asked questions during the date range.",
    )


class Metrics:
    """Define the metrics class."""
    def __init__(self, config: MetricsConfig):
        """Initialize the metrics class."""
        self._openai_config = config.openai_config
        self._archive = config.archive

    def _get_student_messages(self, class_id: UUID, date_range: Optional[DateRange] = None) -> list[str]:
        """Get student records."""
        if date_range is None:
            date_range = DateRange()
        records = self._archive.get_archived_messages(
            class_id=class_id,
            date_range=date_range,
            RecordClass=HumanMessageRecord,
        )
        assert all(isinstance(rec, HumanMessageRecord) for rec in records)
        rec: HumanMessageRecord
        messages = []
        for rec in records:
            messages.append(rec.message)
        return messages

    def _rank_summaries(self, summary: list[str]) -> list[CommonQuestion]:
        """Rank messages."""
        ranked_messages = []
        for rank, message in enumerate(summary, 1):
            msg = CommonQuestion(
                rank=rank,
                appearances_during_period=1,
                question=message,
            )
            ranked_messages.append(msg)
        return ranked_messages

    def get_most_frequently_asked_questions(self, class_id: UUID, date_range: Optional[DateRange] = None) -> Optional[CommonQuestions]:
        """Get the most frequently asked questions."""
        if date_range is None:
            date_range = DateRange()
        messages = self._get_student_messages(class_id, date_range)
        if len(messages) <= 10:
            return
        llm = TaiLLM(self._openai_config)
        messages = llm.summarize_student_messages(messages, as_questions=True)
        common_questions = CommonQuestions(
            class_id=class_id,
            date_range=date_range,
            common_questions=self._rank_summaries(messages)
        )
        return common_questions
