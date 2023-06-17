"""Define the Pinecone database construct."""
import re
from constructs import Construct
from aws_cdk import (
    aws_iam as iam,
    CustomResource,
)
from tai_service.cdk.constructs.construct_helpers import VALID_SECRET_ARN_PATTERN
from tai_service.cdk.constructs.python_lambda_props_builder import (
    PythonLambdaPropsBuilderConfigModel,
    PythonLambdaPropsBuilder,
)


class PineconeDatabase(Construct):
    """Define the Pinecone database construct."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        pinecone_db_api_secret_arn: str,
        lambda_config: PythonLambdaPropsBuilderConfigModel,
        **kwargs,
    ) -> None:
        """Initialize the Pinecone database construct."""
        super().__init__(scope, construct_id, **kwargs)
        self._namer = lambda name: f"{construct_id}-{name}"
        self._secret_arn = pinecone_db_api_secret_arn
        self._lambda_config = lambda_config

    def _validate_secret_arn(self) -> None:
        """Validate the secret ARN."""
        if not re.match(VALID_SECRET_ARN_PATTERN, self._secret_arn):
            raise ValueError(
                f"Invalid secret ARN: {self._secret_arn}. Please provide a valid secret ARN."
            )

    def _create_custom_resource(self) -> CustomResource:
        name = self._namer("custom-resource-db-initializer-lambda")
        self._lambda_config.function_name = name
        lambda_function = PythonLambdaPropsBuilder.get_lambda_function(
            self,
            construct_id=name,
            config=self._lambda_config,
        )
        lambda_function.add_to_role_policy(
            statement=iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                effect=iam.Effect.ALLOW,
                resources=[self._secret_arn],
            )
        )
        custom_resource = CustomResource(
            self,
            id=self._namer("custom-resource"),
            service_token=lambda_function.function_arn,
        )
        return custom_resource
