"""Define errors for the backend."""

class DuplicateResourceError(Exception):
    """Define an error for when a resource already exists."""

    def __init__(self, message: str) -> None:
        """Initialize the error."""
        super().__init__(message)
        self.message = message
