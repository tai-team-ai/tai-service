"""Define schemas for the TAI LLMs."""
from enum import Enum
from pydantic import BaseModel, Field

class TaiTutorName(str, Enum):
    """Define the built-in TAI tutor names."""

    FIN = "fin"
    ALEX = "alex"



class TaiTutor(BaseModel):
    """Define the model for the TAI tutor."""

    name: TaiTutorName = Field(
        ...,
        description="The name of the TAI tutor.",
    )
    system_prompt: str = Field(
        ...,
        description="The system prompt for the TAI tutor.",
    )
