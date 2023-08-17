"""Define schemas for common resources."""
import copy
from uuid import UUID
from datetime import datetime, timedelta
from pydantic import Field, conint
# first imports are for local development, second imports are for deployment
try:
    from .base_schema import BasePydanticModel, EXAMPLE_UUID
    from .tai_schemas import ClassResourceSnippet, EXAMPLE_CLASS_RESOURCE_SNIPPET
except ImportError:
    from routers.base_schema import BasePydanticModel, EXAMPLE_UUID
    from routers.tai_schemas import ClassResourceSnippet, EXAMPLE_CLASS_RESOURCE_SNIPPET


EXAMPLE_BASE_FREQUENTLY_ACCESSED_OBJECTS = {
    "classId": EXAMPLE_UUID,
    "dateRange": {
        "startDate": (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "endDate": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    },
}
EXAMPLE_MOST_FREQUENTLY_ASKED_QUESTION = copy.deepcopy(EXAMPLE_BASE_FREQUENTLY_ACCESSED_OBJECTS)
EXAMPLE_MOST_FREQUENTLY_ASKED_QUESTION.update({
    "commonQuestions": [
        {
            "question": "What is the difference between a vector and a scalar?",
            "rank": 1,
            "appearancesDuringPeriod": 3,
        },
        {
            "question": "What is the difference between a vector and a scalar?",
            "rank": 2,
            "appearancesDuringPeriod": 1,
        },
    ],
})
EXAMPLE_MOST_FREQUENTLY_ACCESSED_RESOURCE = copy.deepcopy(EXAMPLE_BASE_FREQUENTLY_ACCESSED_OBJECTS)
EXAMPLE_MOST_FREQUENTLY_ACCESSED_RESOURCE.update({
    "resources": [
        {
            "resource": EXAMPLE_CLASS_RESOURCE_SNIPPET,
            "rank": 1,
            "appearancesDuringPeriod": 2,
        },
        {
            "resource": EXAMPLE_CLASS_RESOURCE_SNIPPET,
            "rank": 2,
            "appearancesDuringPeriod": 1,
        },
    ],
})

class DateRange(BasePydanticModel):
    """Define a schema for a date range."""
    start_date: datetime = Field(
        default=datetime.utcnow() - timedelta(days=30),
        description="The start date of the date range.",
    )
    end_date: datetime = Field(
        default=datetime.utcnow(),
        description="The end date of the date range.",
    )


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
    resource: ClassResourceSnippet = Field(
        ...,
        description="The resource that was most common during the date range.",
    )


class CommonQuestions(BaseFrequentlyAccessedObjects):
    """Define a schema for common questions."""
    common_questions: list[CommonQuestion] = Field(
        ...,
        description="The list of the most frequently asked questions during the date range.",
    )

    class Config:
        """Configure schema settings."""
        schema_extra = {
            "example": EXAMPLE_MOST_FREQUENTLY_ASKED_QUESTION,
        }


class FrequentlyAccessedResources(BaseFrequentlyAccessedObjects):
    """Define a schema for common resources."""
    resources: list[FrequentlyAccessedResource] = Field(
        ...,
        description="The list of the most frequently accessed resources during the date range.",
    )

    class Config:
        """Configure schema settings."""
        schema_extra = {
            "example": EXAMPLE_MOST_FREQUENTLY_ACCESSED_RESOURCE,
        }
