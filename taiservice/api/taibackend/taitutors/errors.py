"""Define errors for the TAI tutor LLMs."""
from uuid import UUID


class UserTokenLimitError(Exception):
    """Exception raised for errors when user exceeds token limit.

    Attributes:
        user_id -- UUID of the user
        message -- explanation of the error
    """

    def __init__(self, user_id: UUID, message: str = "User is over token limit.") -> None:
        self.user_id = user_id
        self.message = message
        super().__init__(self.message)

    def __str__(self) -> str:
        return f'{self.user_id} -> {self.message}'


class OverContextWindowError(Exception):
    """Exception raised for errors when user exceeds context window.

    Attributes:
        user_id -- UUID of the user
        message -- explanation of the error
    """

    def __init__(self, user_id: UUID, message: str = "User is over context window.") -> None:
        self.user_id = user_id
        self.message = message
        super().__init__(self.message)

    def __str__(self) -> str:
        return f'{self.user_id} -> {self.message}'
