"""Define user data database and schema."""
from datetime import datetime, timedelta, timezone
from uuid import UUID
from abc import ABC, abstractmethod
from pynamodb.exceptions import DoesNotExist
try:
    from .user_data_schemas import UserModel
except ImportError:
    from taibackend.databases.user_data_schemas import UserModel


class UserDB(ABC):
    """
    An interface for a user data database.

    Any concrete implementation of this interface should provide methods for 
    getting the token count of a user, updating it, and to check if adding a 
    certain number of tokens would exceed the maximum token limit per interval.

    The behavior regarding user's token count reset interval and maximum tokens 
    per interval is predefined in the initialization of concrete classes implementing
    this interface. Specifically, the token count will be reset if it hasn't been
    reset in the specified interval, and the maximum token limit per interval should
    not be exceeded.

    Attributes:
        reset_interval: A timedelta object representing the time interval after 
            which the token count of a user is reset.
        max_tokens_per_interval: An integer representing the maximum number of 
            tokens a user can have per reset interval.
    """

    def __init__(self, reset_interval: timedelta, max_tokens_per_interval: int) -> None:
        """
        Initialize the UserDB.

        Args:
            reset_interval: A timedelta object representing the time interval
                after which the token count of a user is reset.
            max_tokens_per_interval: An integer representing the maximum number
                of tokens a user can have per reset interval.
        """
        self._reset_interval = reset_interval
        self._max_tokens_per_interval = max_tokens_per_interval

    @abstractmethod
    def get_user_token_count(self, user_id: UUID) -> int:
        """
        Get the token count for a specific user. 
        
        Args:
            user_id: A UUID object representing user_id.

        This method will create the user model if a user does not exist. Please note that 
        if the token count has not been reset in the specified reset_interval,
        the token count for the user will be reset before the current amount is 
        fetched and returned.
        """

    @abstractmethod
    def update_token_count(self, user_id: UUID, amount: int) -> None:
        """
        Increase the token count for a specific user by the specified amount.

        Args:
            user_id: A UUID object representing user_id.
            amount: An integer amount to increment the token count by.

        Please note this method will also reset the token count if the last update
        was longer ago than the specified reset_interval.
        """

    @abstractmethod
    def is_user_over_token_limit(self, user_id: UUID, new_tokens: int=0) -> bool:
        """
        Check if a user is over the token limit.

        Args:
            user_id: A UUID object representing user_id.
            new_tokens: An optional integer representing the number of new tokens
                that want to be added for the user.

        Returns:
            A boolean indicating whether the user is over the token limit.

        If the user's existing tokens plus the new tokens exceed the maximum token
        limit per interval, this method will return True. If not, it will return
        False. This method will also reset the user's token count if it hasn't been
        reset in the specified reset interval.
        """


class DynamoDB(UserDB):
    """
    An implementation of UserDB interface using DynamoDB as the underlying 
    database to store and retrieve user-related data.
    """

    def get_user_token_count(self, user_id: UUID) -> int:
        user = self._create_or_get_user(user_id)
        self._reset_token_count_if_needed(user)
        return user.daily_token_count

    def update_token_count(self, user_id: UUID, amount: int) -> None:
        user = self._create_or_get_user(user_id)
        self._reset_token_count_if_needed(user)
        user.update(actions=[UserModel.daily_token_count.set(UserModel.daily_token_count + amount)])

    def is_user_over_token_limit(self, user_id: UUID, new_tokens: int=0) -> bool:
        user = self._create_or_get_user(user_id)
        self._reset_token_count_if_needed(user)
        return user.daily_token_count + new_tokens > self._max_tokens_per_interval

    def _create_user(self, user_id: UUID) -> UserModel:
        user = UserModel(str(user_id))
        user.save()
        return user

    def _create_or_get_user(self, user_id: UUID) -> UserModel:
        try:
            return UserModel.get(str(user_id))
        except DoesNotExist:
            return self._create_user(user_id)

    def _reset_token_count_if_needed(self, user: UserModel) -> None:
        if datetime.now(tz=timezone.utc) - user.token_count_last_reset > self._reset_interval:
            user.update(actions=[
                UserModel.daily_token_count.set(0),
                UserModel.token_count_last_reset.set(datetime.now())
            ])
