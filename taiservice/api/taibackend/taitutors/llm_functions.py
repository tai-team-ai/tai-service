"""Define functions that cen be called by the LLM."""
from typing import List
# first imports are for local development, second imports are for deployment
try:
    from ...routers.tai_schemas import ClassResourceSnippet
except (KeyError, ImportError):
    from routers.tai_schemas import ClassResourceSnippet

def get_relevant_class_resource_chunks(student_message: str) -> list[ClassResourceSnippet]:
    """
    Return the class resource chunks that are relevant to the student message.

    Args:
        student_message: This could be any type of message and may not necessarily match any class resource docs.

    Returns:
        The class resource chunks relevant to the student message. If none are found, then an empty list is returned.
    """


def save_student_conversation_topics(most_common_discussion_topics: List[str]) -> None:
    """
    Save the most common topics discussed by students.

    Args:
        most_common_discussion_topics: A list of the most frequently discussed topics among students. This MUST be a list of strings, not dicts.
    """


def save_student_questions(most_common_questions: List[str]) -> None:
    """
    Save the most common questions asked by students.

    Args:
        most_common_questions: A list of the most frequently asked questions among students. This MUST be a list of strings, not dicts.
    """
