"""Define the Pinecone database construct."""
import re
from constructs import Construct
from aws_cdk import (
    aws_iam as iam,
    custom_resources as cr,
    CustomResource,
)
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
        self._secret_arn = pinecone_db_api_secret_arn
        self._lambda_config = lambda_config
        self.custom_resource_provider = self._create_custom_resource()

    def _create_custom_resource(self) -> cr.Provider:
        name = "pinecone-custom-resource-db-initializer-lambda"
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
        provider = cr.Provider(
            self,
            id="custom-resource-provider",
            on_event_handler=lambda_function,
            provider_function_name=name + "-PROVIDER",
        )
        custom_resource = CustomResource(
            self,
            id="custom-resource",
            service_token=provider.service_token,
        )
        return custom_resource
