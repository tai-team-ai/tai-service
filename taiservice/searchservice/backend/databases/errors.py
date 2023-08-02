"""Define errors for the backend."""

class DuplicateClassResourceError(Exception):
    """Define an error for when a resource already exists."""

    def __init__(self, message: str) -> None:
        """Initialize the error."""
        super().__init__(message)
        self.message = message + "\n Either the document has the same hash as another class resource, "\
            "the id already exists in the class, or the resource is in a transient state (e.g. processing). "\
            "Please try again in a few minutes."
