"""Define functions that cen be called by the LLM."""
# first imports are for local development, second imports are for deployment
try:
    from taiservice.api.taibackend.databases.document_db import ClassResourceChunkDocument
except (KeyError, ImportError):
    from taibackend.databases.document_db import ClassResourceChunkDocument

def get_relevant_class_resource_chunks(student_message: str) -> list[ClassResourceChunkDocument]:
    """
    Return the class resource chunks that are relevant to the student message.

    Args:
        student_message: This could be any type of message and may not necessarily match any class resource docs.

    Returns:
        The class resource chunks relevant to the student message. If none are found, then an empty list is returned.
    """
