"""Define errors for the backend."""

class ServerOverloadedError(Exception):
    """Exception raised when the server is overloaded."""
    def __init__(self, message):
        super().__init__(message)
        self.message = message
