"""Define the stack for the frontend server of the T.A.I. service."""
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_iam as iam,
)
from taiservice.cdk.stacks.stack_config_models import StackConfigBaseModel

class TaiFrontendServerStack(Stack):
    """Define the stack for the TAI API service."""

    def __init__(
        self,
        scope: Construct,
        config: StackConfigBaseModel,
    ) -> None:
        """Initialize the stack for the TAI API service."""
        super().__init__(
            scope=scope,
            id=config.stack_id,
            stack_name=config.stack_name,
            description=config.description,
            env=config.deployment_settings.aws_environment,
            tags=config.tags,
            termination_protection=config.termination_protection,
        )
        self._namer = lambda name: f"{config.stack_name}-{name}"
        self._user = iam.User(
            scope=self,
            id=self._namer("frontend-user"),
            user_name=self._namer("frontend-user"),
        )

    @property
    def user(self) -> iam.User:
        """Return the frontend user."""
        return self._user
