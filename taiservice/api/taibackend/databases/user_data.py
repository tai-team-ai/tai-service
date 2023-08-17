"""Define user data database and schema."""
from datetime import datetime
from uuid import UUID
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
from pynamodb.exceptions import DoesNotExist
try:
    from .user_data_schemas import UserModel
except ImportError:
    from taibackend.databases.user_data_schemas import UserModel

class UserDB(ABC):
    @abstractmethod
    def get_user_token_count(self, user_id: UUID) -> int:
        "Get the token count of a user."
        pass

    @abstractmethod
    def update_token_count(self, user_id: UUID, amount: int) -> None:
        "Increment the token count of a user by a specified amount."
        pass

class DynamoDB(UserDB):
    """
    A concrete implementation of UserDB interface that uses DynamoDB as the 
    underlying database to store and retrieve user related data. 

    It wraps around the UserModel DynamoDB model and provides an easy to use 
    high-level API with atomic operations and smart cache invalidation
    based on time intervals.
    """


    def get_user_token_count(self, user_id: UUID) -> int:
        """
        Get a user's token count and reset it if necessary based on time interval.

        This function first checks if the user exists in the database. If not,
        it creates a new user. After that, it checks if the last token count reset 
        was more than 24 hours ago. If so, it resets the token count. Finally,
        it returns the user's current token count.

        Args:
            user_id: A UUID object representing user_id.

        Returns:
            Current token count of the user.
        """
        try:
            user = UserModel.get(str(user_id))
        except DoesNotExist:
            user = self._create_user(user_id)

        if datetime.now() - user.token_count_last_reset > timedelta(hours=24):
            self._reset_user_token_count(user)

        return user.daily_token_count

    def update_token_count(self, user_id: UUID, amount: int) -> None:
        """
        Atomically increment the token count of a user by a specified amount.

        Args:
            user_id: A UUID object representing user_id.
            amount: An integer amount to increment the token count by.
        """
        user = self._create_or_get_user(user_id)
        user.update(actions=[UserModel.daily_token_count.set(UserModel.daily_token_count + amount)])

    def _create_user(self, user_id: UUID) -> UserModel:
        """
        Create a new user in the database with the given user_id.
        
        Args:
            user_id: A UUID object representing user_id.
        
        Returns:
            A new instance of UserModel.
        """
        user = UserModel(str(user_id))
        user.save()
        return user

    def _create_or_get_user(self, user_id: UUID) -> UserModel:
        """
        Create a new user or get an existing user.

        Args:
            user_id: A UUID object representing user_id.

        Returns:
            An instance of UserModel representing a user.
        """
        try:
            return UserModel.get(str(user_id))
        except DoesNotExist:
            return self._create_user(user_id)

    def _reset_user_token_count(self, user: UserModel) -> None:
        """
        Reset the token count and last reset time of a user.
        
        This function uses atomic operations to avoid race conditions.

        Args:
            user: An instance of UserModel representing a user. 
        """
        user.update(actions=[
            UserModel.daily_token_count.set(0),
            UserModel.token_count_last_reset.set(datetime.now())
        ])
