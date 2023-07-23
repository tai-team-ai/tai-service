"""Define schemas for common resources."""
from uuid import UUID
from datetime import date
from pydantic import Field
# first imports are for local development, second imports are for deployment
try:
    from .base_schema import BasePydanticModel
except ImportError:
    from routers.base_schema import BasePydanticModel


# Common Questions
{
    "classId": "550e8400-e29b-41d4-a716-446655440000",
    "dateRange": {
        "startDate": "2021-01-01",
        "endDate": "2021-01-31",
    },
    "commonQuestions": [
        {
            "question": "What is the difference between a vector and a scalar?",
            "rank": 1,
            "appearancesDuringPeriod": 0,
        },
        {
            "question": "What is the difference between a vector and a scalar?",
            "rank": 2,
            "appearancesDuringPeriod": 0,
        },
    ],
}

# Common Resources
{
    "classId": "550e8400-e29b-41d4-a716-446655440000",
    "dateRange": {
        "startDate": "2021-01-01",
        "endDate": "2021-01-31",
    },
    "commonResources": [
        {
            "resource": "https://www.khanacademy.org/math/linear-algebra/vectors-and-spaces/vectors/v/vector-introduction-linear-algebra",
            "rank": 1,
            "appearancesDuringPeriod": 0,
        },
        {
            "resource": "https://www.khanacademy.org/math/linear-algebra/vectors-and-spaces/vectors/v/vector-introduction-linear-algebra",
            "rank": 2,
            "appearancesDuringPeriod": 0,
        },
    ],
}


class DateRange(BasePydanticModel):
    """Define a schema for a date range."""
    startDate: date = Field(
        ...,
        description="The start date of the date range.",
    )
    endDate: date = Field(
        ...,
        description="The end date of the date range.",
    )


class BaseFrequentlyAccessedObjects(BasePydanticModel):
    """Define a base schema for common resources."""
    classId: UUID = Field(
        ...,
        description="The ID that the common resource belongs to.",
    )
    dateRange: DateRange = Field(
        ...,
        description="The date range over which the appearances of the common resource are counted.",
    )


class BaseFrequentlyAccessedObject(BasePydanticModel):
    """Define a base schema for ranked common resources."""
    rank: int = Field(
        ...,
        description="The rank of the object when ranked by appearances during the date range.",
    )
    appearancesDuringPeriod: int = Field(
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
    commonQuestions: list[CommonQuestion] = Field(
        ...,
        description="The list of the most frequently asked questions during the date range.",
    )


class CommonResource(BaseFrequentlyAccessedObject):
    """Define a schema for a common resource."""
    resource: str = Field(
        ...,
        description="The resource that was most common during the date range.",
    )


class CommonResources(BaseFrequentlyAccessedObjects):
    """Define a schema for common resources."""
    commonResources: list[CommonResource] = Field(
        ...,
        description="The list of the most frequently accessed resources during the date range.",
    )
